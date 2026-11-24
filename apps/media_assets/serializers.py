from django.conf import settings
from rest_framework import serializers

from . import storage
from .models import Media_asset


def variant_url(asset, variant_name):
    """CDN URL for a generated version, or None if the asset isn't ready."""
    variant = (asset.variants or {}).get(variant_name)
    if asset.status != Media_asset.Status.READY or not variant:
        return None
    return storage.public_url(variant['key'])


class ImageUploadRequestSerializer(serializers.Serializer):
    """Input for POST /media/uploads/ (images)."""

    file_name = serializers.CharField(max_length=500)
    mime_type = serializers.CharField(max_length=100)
    file_size = serializers.IntegerField(min_value=1)

    def validate_mime_type(self, value):
        if value not in settings.MEDIA_ALLOWED_IMAGE_TYPES:
            allowed = ', '.join(sorted(settings.MEDIA_ALLOWED_IMAGE_TYPES))
            raise serializers.ValidationError(f'Unsupported image type. Allowed: {allowed}.')
        return value

    def validate_file_size(self, value):
        max_bytes = settings.MEDIA_MAX_IMAGE_BYTES
        if value > max_bytes:
            raise serializers.ValidationError(
                f'Image is too large. The maximum is {max_bytes // (1024 * 1024)} MB.'
            )
        return value


class MediaAssetSerializer(serializers.ModelSerializer):
    """Asset details plus ready-to-use CDN URLs. Only alt_text is writable."""

    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.name', read_only=True)

    class Meta:
        model = Media_asset
        fields = [
            'id',
            'media_type',
            'status',
            'file_name',
            'file_size',
            'mime_type',
            'width',
            'height',
            'alt_text',
            'failure_reason',
            'url',
            'thumbnail_url',
            'uploaded_by',
            'uploaded_by_name',
            'created_at',
        ]
        read_only_fields = [field for field in fields if field != 'alt_text']

    def validate_alt_text(self, value):
        return value.strip()

    def get_url(self, obj):
        return variant_url(obj, 'large')

    def get_thumbnail_url(self, obj):
        return variant_url(obj, 'thumb')


class MediaImageSummarySerializer(serializers.ModelSerializer):
    """
    What content needs to display an image (blog covers, later video thumbnails).
    No internal details (filename, size, uploader): this also reaches the public site.
    """

    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    width = serializers.SerializerMethodField()
    height = serializers.SerializerMethodField()

    class Meta:
        model = Media_asset
        fields = ['id', 'url', 'thumbnail_url', 'width', 'height', 'alt_text']
        read_only_fields = fields

    def get_url(self, obj):
        return variant_url(obj, 'large')

    def get_thumbnail_url(self, obj):
        return variant_url(obj, 'thumb')

    # dimensions of the 'large' version, which is what `url` points to
    def get_width(self, obj):
        return (obj.variants or {}).get('large', {}).get('width')

    def get_height(self, obj):
        return (obj.variants or {}).get('large', {}).get('height')


class VideoUploadStartSerializer(serializers.Serializer):
    video = serializers.UUIDField()
    file_name = serializers.CharField(max_length=255)
    file_size = serializers.IntegerField(min_value=1)
    mime_type = serializers.CharField(max_length=100)

    def validate_file_size(self,value):
        if value > settings.MEDIA_MAX_VIDEO_BYTES:
            limit_mb = settings.MEDIA_MAX_VIDEO_BYTES // (1024 * 1024)
            raise serializers.ValidationError(f'Videos must be {limit_mb} MB or smaller.')
        return value


    def validate_mime_type(self, value):
        if value not in settings.MEDIA_ALLOWED_VIDEO_TYPES:
            raise serializers.ValidationError('Upload an MP4 or MOV video.')
        return value


    def validate_video(self, value):
        # imported here: media_assets shouldn't import videos at load time
        from apps.moderation.rules import get_edit_denial
        from apps.videos.models import Video

        user = self.context['request'].user
        try:
            video = Video.objects.visible_to(user).get(pk=value)
        except Video.DoesNotExist:
            raise serializers.ValidationError('Video not found.')

        if video.source_type != Video.SourceType.UPLOAD:
            raise serializers.ValidationError('This video uses a link, not an uploaded file.')

        denial = get_edit_denial(user, video)
        if denial:
            raise serializers.ValidationError(denial)

        if video.status in (Video.Status.PUBLISHED,Video.Status.ARCHIVED):
            raise serializers.ValidationError(
                "The video file can't be replaced after publishing. Create a new video instead."
            )

        return video


class VideoPartsSerializer(serializers.Serializer):
    part_numbers = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=100,
    )


class VideoPartSerializer(serializers.Serializer):
    part_number = serializers.IntegerField(min_value=1)
    etag = serializers.CharField(max_length=200)


class VideoCompleteSerializer(serializers.Serializer):
    parts = VideoPartSerializer(many=True, allow_empty=False)