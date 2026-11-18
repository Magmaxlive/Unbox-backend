import os
from io import BytesIO

from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

from . import storage
from .models import Media_asset

Status = Media_asset.Status

# Pillow format name -> the MIME type we accept for it
PILLOW_FORMAT_TO_MIME = {
    'JPEG': 'image/jpeg',
    'PNG': 'image/png',
    'WEBP': 'image/webp',
}

# Protects against "decompression bombs": small files that decode into
# enormous images. Checked from the header, before decoding.
MAX_IMAGE_PIXELS = 50_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

WEBP_QUALITY = 82


class ImageProcessingError(Exception):
    """The uploaded file is unusable. The message is shown to the uploader."""


# ── keys and names ──

def build_original_key(asset_id, extension, when=None):
    """originals/2026/11/<uuid>.jpg: unguessable, never collides, never uses the user's filename."""
    when = when or timezone.now()
    return f'{storage.ORIGINALS_PREFIX}{when:%Y/%m}/{asset_id}.{extension}'


def build_variant_key(asset, variant_name):
    """originals/2026/11/<uuid>.jpg -> public/2026/11/<uuid>-<variant>.webp"""
    base = asset.storage_key.replace(storage.ORIGINALS_PREFIX, storage.PUBLIC_PREFIX, 1)
    base = base.rsplit('.', 1)[0]
    return f'{base}-{variant_name}.webp'


def clean_display_name(file_name):
    """Keep only the base name (no client paths), trimmed to fit the field."""
    name = os.path.basename((file_name or '').replace('\\', '/')).strip()
    return (name or 'upload')[:255]


# ── step 1: request an upload ──

def create_image_upload(user, file_name, mime_type, file_size):
    """
    Create a Media_asset in 'uploading' state and a presigned form for the browser.
    Type and size were validated by the serializer; S3 enforces them again.
    Returns (asset, presigned) where presigned = {"url": ..., "fields": {...}}.
    """
    extension = settings.MEDIA_ALLOWED_IMAGE_TYPES[mime_type]

    asset = Media_asset(
        uploaded_by=user,
        file_name=clean_display_name(file_name),
        file_size=file_size,
        mime_type=mime_type,
        media_type=Media_asset.MediaType.IMAGE,
        status=Status.UPLOADING,
        bucket_name=storage.get_bucket_name(),
    )
    # the id is generated on instantiation, so the key can use it before saving
    asset.storage_key = build_original_key(asset.id, extension)
    asset.save()

    presigned = storage.create_presigned_upload(
        key=asset.storage_key,
        content_type=mime_type,
        # the size the browser claimed (already <= the configured maximum):
        # S3 refuses anything larger than what was declared
        max_bytes=file_size,
    )

    return asset, presigned


# ── step 2: verify and process ──

def _open_verified_image(data, expected_mime):
    """Open the bytes as an image, proving it's genuine and of the declared type."""
    try:
        # verify() checks integrity but leaves the image unusable, so reopen after
        with Image.open(BytesIO(data)) as probe:
            probe.verify()

        image = Image.open(BytesIO(data))

        # dimensions come from the header: refuse huge images before decoding
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise ImageProcessingError('The image dimensions are too large.')

        image.load()
    except ImageProcessingError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError) as error:
        raise ImageProcessingError('The file is not a valid image.') from error

    actual_mime = PILLOW_FORMAT_TO_MIME.get(image.format)
    if actual_mime != expected_mime:
        raise ImageProcessingError('The file type does not match its contents.')

    return image


def _prepare_for_web(image):
    """
    Apply EXIF rotation (phone photos), keep the colour profile, and convert to
    a mode WebP supports. EXIF itself is not carried over (privacy: GPS etc.).
    """
    icc_profile = image.info.get('icc_profile')

    image = ImageOps.exif_transpose(image)

    has_transparency = (
        image.mode in ('RGBA', 'LA')
        or (image.mode == 'P' and 'transparency' in image.info)
    )
    if has_transparency:
        image = image.convert('RGBA')
    elif image.mode != 'RGB':
        image = image.convert('RGB')

    return image, icc_profile


def _render_webp(image, max_width, icc_profile):
    """Resize down to max_width (never up) and encode as WebP."""
    if image.width > max_width:
        new_height = max(1, round(image.height * max_width / image.width))
        image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    save_options = {'format': 'WEBP', 'quality': WEBP_QUALITY, 'method': 4}
    if icc_profile:
        save_options['icc_profile'] = icc_profile
    image.save(buffer, **save_options)

    return buffer.getvalue(), image.width, image.height


def complete_image_upload(asset):
    """
    Verify the uploaded original and generate the public WebP versions.
    Safe to call repeatedly: only one call does the work.
    """
    # Claim the work: only an 'uploading' asset moves to 'processing'.
    claimed = Media_asset.objects.filter(
        pk=asset.pk, status=Status.UPLOADING,
    ).update(status=Status.PROCESSING)

    if not claimed:
        asset.refresh_from_db()
        if asset.status == Status.READY:
            return asset
        if asset.status == Status.FAILED:
            raise ValidationError({'detail': asset.failure_reason or 'This upload failed. Please upload the image again.'})
        raise ValidationError({'detail': 'This upload is already being processed.'})

    asset.refresh_from_db()

    info = storage.get_object_info(asset.storage_key)
    if info is None:
        # not uploaded yet: allow the client to finish the upload and retry
        Media_asset.objects.filter(pk=asset.pk).update(status=Status.UPLOADING)
        raise ValidationError({'detail': 'The file has not been uploaded yet.'})

    uploaded_keys = []
    try:
        size_limit = min(asset.file_size, settings.MEDIA_MAX_IMAGE_BYTES)
        if info['size'] > size_limit:
            raise ImageProcessingError('The uploaded file is larger than declared.')

        data = storage.read_object(asset.storage_key, max_bytes=settings.MEDIA_MAX_IMAGE_BYTES)
        image = _open_verified_image(data, asset.mime_type)
        image, icc_profile = _prepare_for_web(image)

        variants = {}
        for variant_name, max_width in settings.MEDIA_IMAGE_VARIANTS.items():
            content, width, height = _render_webp(image, max_width, icc_profile)
            key = build_variant_key(asset, variant_name)
            storage.upload_bytes(key, content, 'image/webp')
            uploaded_keys.append(key)
            variants[variant_name] = {
                'key': key,
                'width': width,
                'height': height,
                'size': len(content),
            }

    except (ImageProcessingError, ValueError) as error:
        # unusable file: remove what we stored and record why
        storage.delete_objects([asset.storage_key, *uploaded_keys])
        asset.status = Status.FAILED
        asset.failure_reason = str(error)[:300]
        asset.save(update_fields=['status', 'failure_reason', 'updated_at'])
        raise ValidationError({'detail': asset.failure_reason})

    except Exception:
        # unexpected (e.g. S3 unavailable): leave it retryable
        Media_asset.objects.filter(pk=asset.pk).update(status=Status.UPLOADING)
        raise

    # dimensions after EXIF rotation, i.e. as displayed
    asset.width = image.width
    asset.height = image.height
    asset.file_size = info['size']
    asset.variants = variants
    asset.status = Status.READY
    asset.failure_reason = ''
    asset.save(update_fields=[
        'width', 'height', 'file_size', 'variants', 'status', 'failure_reason', 'updated_at',
    ])

    return asset