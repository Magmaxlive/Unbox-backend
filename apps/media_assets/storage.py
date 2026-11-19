"""
The only module that talks to S3. Views and services call these functions;
nothing else imports boto3.

Bucket layout:
  originals/...  exactly what users uploaded (never served by the CDN)
  public/...     generated files, served by CloudFront (origin path /public)
"""

from functools import lru_cache

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

PUBLIC_PREFIX = 'public/'
ORIGINALS_PREFIX = 'originals/'

# Generated files never change at the same key (new UUID per upload),
# so browsers and CloudFront may cache them for a year.
IMMUTABLE_CACHE_CONTROL = 'public, max-age=31536000, immutable'


@lru_cache(maxsize=1)
def get_s3_client():
    if not settings.AWS_S3_BUCKET or not settings.AWS_S3_REGION:
        raise ImproperlyConfigured(
            'AWS_S3_BUCKET and AWS_S3_REGION must be set (see .env).'
        )

    client_kwargs = {
        'region_name': settings.AWS_S3_REGION,
        'config': Config(
            signature_version='s3v4',
            s3={'addressing_style': 'virtual'},
        ),
    }

    # Explicit keys if configured; otherwise boto3's default lookup
    # (e.g. an IAM role in production).
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
        client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY

    return boto3.client('s3', **client_kwargs)


def get_bucket_name():
    return settings.AWS_S3_BUCKET


def create_presigned_upload(key, content_type, max_bytes, expires_in=None):
    """
    Short-lived form the browser posts the file to, directly to S3.
    S3 itself rejects a different content type or a file larger than max_bytes.

    Returns {"url": ..., "fields": {...}}. The browser sends every field,
    then the file as the LAST form field, named "file".
    """
    return get_s3_client().generate_presigned_post(
        Bucket=get_bucket_name(),
        Key=key,
        Fields={'Content-Type': content_type},
        Conditions=[
            {'Content-Type': content_type},
            ['content-length-range', 1, max_bytes],
        ],
        ExpiresIn=expires_in or settings.MEDIA_UPLOAD_URL_EXPIRY_SECONDS,
    )


def get_object_info(key):
    """
    Metadata for an object, or None if it doesn't exist.
    (Needs s3:ListBucket so a missing key returns 404 rather than 403.)
    """
    try:
        response = get_s3_client().head_object(Bucket=get_bucket_name(), Key=key)
    except ClientError as error:
        code = error.response.get('Error', {}).get('Code', '')
        if code in ('404', 'NoSuchKey', 'NotFound'):
            return None
        raise

    return {
        'size': response['ContentLength'],
        'content_type': response.get('ContentType', ''),
        'etag': response.get('ETag', '').strip('"'),
    }


def read_object(key, max_bytes):
    """
    Download an object into memory, refusing anything larger than max_bytes
    (a safety net even though S3 enforced the limit at upload).
    """
    response = get_s3_client().get_object(Bucket=get_bucket_name(), Key=key)
    data = response['Body'].read(max_bytes + 1)

    if len(data) > max_bytes:
        raise ValueError(f'Object {key} exceeds the {max_bytes}-byte limit.')

    return data


def upload_bytes(key, data, content_type, cache_control=IMMUTABLE_CACHE_CONTROL):
    """Write a file we generated (e.g. a resized image)."""
    get_s3_client().put_object(
        Bucket=get_bucket_name(),
        Key=key,
        Body=data,
        ContentType=content_type,
        CacheControl=cache_control,
    )


def delete_objects(keys):
    """Delete many objects at once (S3 allows up to 1000 per call)."""
    keys = [key for key in keys if key]
    client = get_s3_client()

    for start in range(0, len(keys), 1000):
        batch = keys[start:start + 1000]
        client.delete_objects(
            Bucket=get_bucket_name(),
            Delete={'Objects': [{'Key': key} for key in batch], 'Quiet': True},
        )


def public_url(key):
    """
    CloudFront URL for a key under public/.
    CloudFront's origin path is /public, so the prefix is not part of the URL.
    """
    if not key or not key.startswith(PUBLIC_PREFIX):
        raise ValueError(f'Only keys under {PUBLIC_PREFIX} are publicly served: {key!r}')

    if not settings.MEDIA_CDN_URL:
        raise ImproperlyConfigured('MEDIA_CDN_URL must be set (see .env).')

    return f'{settings.MEDIA_CDN_URL}/{key[len(PUBLIC_PREFIX):]}'