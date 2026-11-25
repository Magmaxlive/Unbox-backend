import os
from io import BytesIO
import math
import uuid
import logging
from decimal import Decimal
from django.core.cache import cache
from . import transcoding

from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError
from django.db import transaction
from botocore.exceptions import ClientError
import contextvars
from contextlib import contextmanager

from . import storage
from .models import Media_asset

logger = logging.getLogger(__name__)

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


# MP4/MOV files are made of "boxes": bytes 4-8 name the first one.
# Modern files start with "ftyp"; some older QuickTime files with these.
MP4_MOV_FIRST_BOXES = {b'ftyp', b'moov', b'wide', b'free', b'mdat', b'skip', b'pnot'}
MIN_VIDEO_SECONDS = 1


def _looks_like_mp4_or_mov(header):
    return len(header) >= 8 and header[4:8] in MP4_MOV_FIRST_BOXES


# ── Videos: multipart uploads ──

def video_part_count(file_size):
    return max(1, math.ceil(file_size / settings.MEDIA_VIDEO_PART_SIZE))


def _video_original_key(extension):
    now = timezone.now()
    return f'originals/{now:%Y/%m}/{uuid.uuid4()}.{extension}'


def create_video_upload(user, video, file_name, file_size, mime_type):
    """
    Start a multipart upload for `video` and attach the new asset to it.
    The browser then uploads parts straight to S3.
    """
    extension = settings.MEDIA_ALLOWED_VIDEO_TYPES[mime_type]
    key = _video_original_key(extension)
    upload_id = storage.create_multipart_upload(key, mime_type)

    with transaction.atomic():
        asset = Media_asset.objects.create(
            uploaded_by=user,
            bucket_name=settings.AWS_S3_BUCKET,
            storage_key=key,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            media_type=Media_asset.MediaType.VIDEO,
            status=Media_asset.Status.UPLOADING,
            multipart_upload_id=upload_id,
        )

        # the new file replaces any earlier upload (that asset becomes unused
        # and is removed later by cleanup_media)
        video.media_asset = asset
        video.duration = None
        video.save(update_fields=['media_asset', 'duration', 'updated_at'])

    return asset


def sign_video_parts(asset, part_numbers):
    part_count = video_part_count(asset.file_size)
    if any(not 1 <= number <= part_count for number in part_numbers):
        raise ValidationError({'part_numbers': f'Part numbers must be between 1 and {part_count}.'})

    return [
        {
            'part_number': number,
            'url': storage.presign_upload_part(
                asset.storage_key,
                asset.multipart_upload_id,
                number,
                settings.MEDIA_VIDEO_PART_URL_EXPIRY_SECONDS,
            ),
        }
        for number in part_numbers
    ]


def _fail_video_upload(asset, reason):
    if asset.multipart_upload_id:
        storage.abort_multipart_upload(asset.storage_key, asset.multipart_upload_id)

    asset.status = Media_asset.Status.FAILED
    asset.failure_reason = reason
    asset.multipart_upload_id = ''
    asset.save(update_fields=['status', 'failure_reason', 'multipart_upload_id', 'updated_at'])


def complete_video_upload(asset, parts):
    """
    Join the parts, verify the file size, and hand the video to processing.
    Safe against double completion: the asset is claimed first.
    """
    part_count = video_part_count(asset.file_size)
    numbers = sorted(part['part_number'] for part in parts)
    if numbers != list(range(1, part_count + 1)):
        raise ValidationError({'parts': f'All {part_count} parts are needed to finish this upload.'})

    # claim: only one request can move it out of "uploading"
    claimed = Media_asset.objects.filter(
        pk=asset.pk,
        status=Media_asset.Status.UPLOADING,
    ).update(status=Media_asset.Status.PROCESSING)
    if not claimed:
        raise ValidationError({'detail': 'This upload is no longer in progress.'})
    asset.refresh_from_db()

    try:
        storage.complete_multipart_upload(
            asset.storage_key,
            asset.multipart_upload_id,
            sorted(parts, key=lambda part: part['part_number']),
        )
    except ClientError:
        _fail_video_upload(asset, 'The upload could not be completed.')
        raise ValidationError({'detail': 'The upload could not be completed. Please upload the video again.'})

    actual_size = storage.get_object_size(asset.storage_key)
    if actual_size != asset.file_size:
        storage.delete_objects([asset.storage_key])
        asset.multipart_upload_id = ''
        _fail_video_upload(asset, 'The uploaded file did not match the expected size.')
        raise ValidationError({'detail': 'The uploaded file did not match the expected size. Please upload it again.'})

    asset.multipart_upload_id = ''
    asset.save(update_fields=['multipart_upload_id', 'updated_at'])

        # a renamed image or document is refused before we pay for processing
    if not _looks_like_mp4_or_mov(storage.read_object_start(asset.storage_key)):
        storage.delete_objects([asset.storage_key])
        asset.multipart_upload_id = ''
        _fail_video_upload(asset, "This file isn't an MP4 or MOV video.")
        raise ValidationError({'detail': "This file isn't an MP4 or MOV video. Please upload a different file."})

    start_video_processing(asset)

    return asset


def abort_video_upload(asset):
    _fail_video_upload(asset, 'Upload cancelled.')



# ── Videos: processing (MediaConvert) ──

PROCESSING_FAILED_REASON = "We couldn't process this video. Make sure it's a valid MP4 or MOV file."


def start_video_processing(asset):
    """
    Start the MediaConvert job. If AWS can't start it right now, the asset
    stays "processing" without a job id and the next status check retries.
    """
    try:
        job_id = transcoding.create_job(asset)
    except ClientError:
        logger.exception('Could not start MediaConvert job for asset %s', asset.pk)
        return asset

    asset.processing_job_id = job_id
    asset.save(update_fields=['processing_job_id', 'updated_at'])
    return asset


def _fail_processed_video(asset, reason, extra_keys=()):
    """Mark failed and delete the original plus any outputs."""
    storage.delete_objects([asset.storage_key, *extra_keys])
    asset.status = Media_asset.Status.FAILED
    asset.failure_reason = reason
    asset.save(update_fields=['status', 'failure_reason', 'duration', 'updated_at'])


def _finish_video_processing(asset, job):
    from apps.videos.models import Video   # avoid importing videos at load time

    output = job['OutputGroupDetails'][0]['OutputDetails'][0]   # the MP4 (first output)
    duration = (Decimal(output.get('DurationInMs', 0)) / 1000).quantize(Decimal('0.01'))
    video_details = output.get('VideoDetails', {})

    mp4_key = transcoding.mp4_key(asset)
    poster_candidates = transcoding.poster_keys(asset)
    poster_key = next((key for key in poster_candidates if storage.get_object_size(key)), '')

    asset.duration = duration

        # a still image or broken file can come out as a near-zero-length "video"
    if duration < MIN_VIDEO_SECONDS or not video_details.get('WidthInPx'):
        _fail_processed_video(
            asset,
            PROCESSING_FAILED_REASON,
            extra_keys=[mp4_key, *poster_candidates],
        )
        return asset

    if duration > Video.MAX_DURATION_SECONDS:
        _fail_processed_video(
            asset,
            f'Videos must be {Video.MAX_DURATION_SECONDS} seconds or shorter. '
            f'This one is {round(duration)} seconds.',
            extra_keys=[mp4_key, *poster_candidates],
        )
        return asset

    with transaction.atomic():
        asset.status = Media_asset.Status.READY
        asset.width = video_details.get('WidthInPx')
        asset.height = video_details.get('HeightInPx')
        asset.variants = {'mp4': mp4_key, 'poster': poster_key}
        asset.failure_reason = ''
        asset.save(update_fields=[
            'status', 'width', 'height', 'duration', 'variants', 'failure_reason', 'updated_at',
        ])

        # the displayed length on every video using this file
        asset.videos.update(duration=duration)

    return asset


def refresh_video_processing(asset, force=False):
    """
    Check a processing video's MediaConvert job and apply the result.
    Throttled to one AWS call per asset per MEDIA_VIDEO_STATUS_CHECK_SECONDS
    (unless force=True, used by the management command).
    """
    if asset.media_type != Media_asset.MediaType.VIDEO or asset.status != Media_asset.Status.PROCESSING:
        return asset

    if not force and not cache.add(
        f'video-processing-check:{asset.pk}', 1, settings.MEDIA_VIDEO_STATUS_CHECK_SECONDS
    ):
        return asset

    # the job never started (AWS hiccup): try again
    if not asset.processing_job_id:
        return start_video_processing(asset)

    try:
        job = transcoding.get_job(asset.processing_job_id)
    except ClientError:
        logger.exception('Could not check MediaConvert job %s', asset.processing_job_id)
        return asset

    status = job['Status']

    if status == 'COMPLETE':
        return _finish_video_processing(asset, job)

    if status in ('ERROR', 'CANCELED'):
        logger.warning(
            'MediaConvert job %s for asset %s ended %s: %s',
            asset.processing_job_id, asset.pk, status, job.get('ErrorMessage', ''),
        )
        _fail_processed_video(
            asset,
            PROCESSING_FAILED_REASON,
            extra_keys=[transcoding.mp4_key(asset), *transcoding.poster_keys(asset)],
        )

    # SUBMITTED / PROGRESSING: nothing to do yet
    return asset


# ── Videos: publishing to the CDN ──

PUBLIC_CACHE_CONTROL = 'public, max-age=3600'
VARIANT_CONTENT_TYPES = {'mp4': 'video/mp4', 'poster': 'image/jpeg'}


def publish_video_files(asset):
    """Copy the processed MP4 and poster into public/ for the CDN."""
    if asset.status != Media_asset.Status.READY:
        raise ValidationError({'media_asset': 'The video is still processing. Please try again in a moment.'})

    public_variants = {}
    for name, content_type in VARIANT_CONTENT_TYPES.items():
        key = asset.variants.get(name)
        if not key:
            continue
        public_key = f'public/{key}'
        storage.copy_object(key, public_key, content_type, PUBLIC_CACHE_CONTROL)
        public_variants[f'public_{name}'] = public_key

    asset.variants = {**asset.variants, **public_variants}
    asset.save(update_fields=['variants', 'updated_at'])


def unpublish_video_files(asset):
    """Delete the public copies and clear them from the CDN cache."""
    public_keys = [
        asset.variants.get(f'public_{name}')
        for name in VARIANT_CONTENT_TYPES
        if asset.variants.get(f'public_{name}')
    ]
    if not public_keys:
        return

    storage.delete_objects(public_keys)
    # one wildcard path per video (CloudFront counts it as one path)
    queue_cdn_invalidation([f'public/{transcoding.output_prefix(asset)}*'])

    asset.variants = {
        name: key for name, key in asset.variants.items()
        if not name.startswith('public_')
    }
    asset.save(update_fields=['variants', 'updated_at'])


# ── CDN invalidations: after commit, batched during bulk actions ──

_cdn_batch = contextvars.ContextVar('cdn_invalidation_batch',default=None)

def _invalidate_now(keys):
    """Best effort: the files are already gone; a stale cache expires within an hour."""
    if not keys:
        return
    try:
        storage.invalidate_cdn(keys)
    except ClientError:
        logger.exception('CDN invalidation failed for %s',keys)


def queue_cdn_invalidation(keys):
    """Invalidate after the current transaction commits, or at the end of a batch."""
    batch = _cdn_batch.get()
    if batch is not None:
        batch.extend(keys)
        return
    transaction.on_commit(lambda:_invalidate_now(list(keys))) 


@contextmanager
def batched_cdn_invalidation():
   """Collect every invalidation inside this block and send them in one request."""
   keys = []
   token = _cdn_batch.set(keys)
   try:
       yield
   finally:
       _cdn_batch.reset(token)
       _invalidate_now(keys) 