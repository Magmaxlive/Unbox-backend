import os
from django.conf import settings
from django.utils import timezone

from . import storage
from .models import Media_asset

def build_original_key(asset_id,extension,when=None):
    """originals/2026/11/<uuid>.jpg: unguessable, never collides, never uses the user's filename."""
    when = when or timezone.now()
    return f'{storage.ORIGINALS_PREFIX}{when:%Y/%m}/{asset_id}.{extension}'


def clean_display_name(file_name):
    """Keep only the base name (no client paths), trimmed to fit the field."""
    name = os.path.basename((file_name or '').replace('\\', '/')).strip()
    return (name or 'upload')[:255]

def create_image_upload(user,file_name,mime_type,file_size):
    """
    Create a Media_asset in 'uploading' state and a presigned form for the browser.
    Type and size were validated by the serializer; S3 enforces them again.
    Returns (asset, presigned) where presigned = {"url": ..., "fields": {...}}.
    """
    extension = settings.MEDIA_ALLOWED_IMAGE_TYPES[mime_type]

    asset = Media_asset(
        uploaded_by = user,
        file_name = clean_display_name(file_name),
        file_size = file_size,
        mime_type = mime_type,
        media_type = Media_asset.MediaType.IMAGE,
        status = Media_asset.Status.UPLOADING,
        bucket_name = storage.get_bucket_name()
    )

    # the id is generated on instantiation, so the key can use it before saving
    asset.storage_key = build_original_key(asset.id,extension)
    asset.save()

    presigned = storage.create_presigned_upload(
        key=asset.storage_key,
        content_type=mime_type,
        max_bytes=file_size
    )

    return asset, presigned