from django.conf import settings
from rest_framework import serializers

from . import storage
from .models import Media_asset

class ImageUploadRequestSerializer(serializers.Serializer):
    """Input for POST /media/uploads/ (images)."""

    file_name = serializers.CharField(max_length=500)
    mime_type = serializers.CharField(max_length=100)
    file_size = serializers.IntegerField(min_value=1)

    def validate_mime_type(self,value):
        if value not in settings.MEDIA_ALLOWED_IMAGE_TYPES:
            allowed = ', '.join(sorted(settings.MEDIA_ALLOWED_IMAGE_TYPES))
            raise serializers.ValidationError(f'Unsupported image type. Allowed :{allowed}.')
        return value

    def validate_file_size(self,value):
        max_bytes = settings.MEDIA_MAX_IMAGE_BYTES
        if value > max_bytes:
            raise serializers.ValidationError(
                f'Image is too large. The maximum is {max_bytes // (1024 * 1024)} MB.'
            )
        return value


class MediaAssetSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

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
            'created_at', 
        ]
        read_only_fields = fields

    def _variant_url(self,obj,name):
        variant = (obj.variants or {}).get(name)
        if obj.status != Media_asset.Status.READY or not variant:
            return None
        return storage.public_url(variant['key'])

    def get_url(self,obj):
        return self._variant_url(obj,'large')

    def get_thumbnail_url(self,obj):
        return self._variant_url(obj,'thumb')