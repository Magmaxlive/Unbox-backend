"""
The only module that talks to S3. Views and services call these functions;
nothing else imports boto3.

Bucket layout:
  originals/...  exactly what users uploaded (never served by the CDN)
  public/...     generated files, served by CloudFront (origin path /public)
"""

from functools import lru_cache
import uuid
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


def list_keys(prefix):
    """Every object key under a prefix (e.g. one video's output folder)."""
    keys = []
    paginator = get_s3_client().get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=settings.AWS_S3_BUCKET, Prefix=prefix):
        keys.extend(item['Key'] for item in page.get('Contents',[]))
    return keys


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


def create_multipart_upload(key, content_type):
    """Start an S3 multipart upload; returns S3's UploadId."""
    response = get_s3_client().create_multipart_upload(
        Bucket=settings.AWS_S3_BUCKET,
        Key=key,
        ContentType=content_type,
    )
    return response['UploadId']


def presign_upload_part(key, upload_id, part_number, expires_in):
    """A URL the browser can PUT one part to."""
    return get_s3_client().generate_presigned_url(
        'upload_part',
        Params={
            'Bucket': settings.AWS_S3_BUCKET,
            'Key': key,
            'UploadId': upload_id,
            'PartNumber': part_number,
        },
        ExpiresIn=expires_in,
    )


def complete_multipart_upload(key, upload_id, parts):
    """Join the uploaded parts. `parts`: [{'part_number': 1, 'etag': '"…"'}, …] in order."""
    get_s3_client().complete_multipart_upload(
        Bucket=settings.AWS_S3_BUCKET,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={
            'Parts': [{'PartNumber': p['part_number'], 'ETag': p['etag']} for p in parts],
        },
    )


def abort_multipart_upload(key, upload_id):
    """Discard an unfinished upload and its parts. Already gone is fine."""
    try:
        get_s3_client().abort_multipart_upload(
            Bucket=settings.AWS_S3_BUCKET,
            Key=key,
            UploadId=upload_id,
        )
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') != 'NoSuchUpload':
            raise


def get_object_size(key):
    """Size in bytes, or None if the object doesn't exist."""
    try:
        response = get_s3_client().head_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') in ('404', 'NoSuchKey', 'NotFound'):
            return None
        raise
    return response['ContentLength']

def read_object_start(key, length=16):
    """The first `length` bytes of an object (a ranged GET; doesn't download the file)."""
    response = get_s3_client().get_object(
        Bucket=settings.AWS_S3_BUCKET,
        Key=key,
        Range=f'bytes=0-{length - 1}',
    )
    return response['Body'].read()


# cdn
def copy_object(source_key, destination_key, content_type, cache_control):
    """Copy within the bucket (used to publish processed files into public/)."""
    get_s3_client().copy_object(
        Bucket=settings.AWS_S3_BUCKET,
        Key=destination_key,
        CopySource={'Bucket': settings.AWS_S3_BUCKET, 'Key': source_key},
        MetadataDirective='REPLACE',
        ContentType=content_type,
        CacheControl=cache_control,
    )


def presign_get(key, expires_in):
    """A temporary read link for a private file (dashboard previews)."""
    return get_s3_client().generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.AWS_S3_BUCKET, 'Key': key},
        ExpiresIn=expires_in,
    )


def invalidate_cdn(keys):
    """
    Tell CloudFront to drop cached copies of these public/ files.
    The distribution's origin path is /public, so URLs omit that prefix.
    """
    if not keys or not settings.CLOUDFRONT_DISTRIBUTION_ID:
        return

    paths = ['/' + key.removeprefix('public/') for key in keys]

    boto3.client(
        'cloudfront',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    ).create_invalidation(
        DistributionId=settings.CLOUDFRONT_DISTRIBUTION_ID,
        InvalidationBatch={
            'Paths': {'Quantity': len(paths), 'Items': paths},
            'CallerReference': str(uuid.uuid4()),
        },
    )