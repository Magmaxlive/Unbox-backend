from rest_framework import serializers
from .models import Media_asset

def validate_image_asset(value,request,label='Image'):
    """
    Shared check for images attached to content (blog cover, video thumbnail):
    must be an image, processed and ready, and (for non-admins) your own upload.
    """
    if value is None:
        return value

    if value.media_type != Media_asset.MediaType.IMAGE:
        raise serializers.ValidationError(f'{label} must be an image.')

    if value.status != Media_asset.Status.READY:
        raise serializers.ValidationError(f'{label} is not ready for use.')

    if (
        request
        and getattr(request.user, 'role', None) != 'admin'
        and value.uploaded_by_id != request.user.id
    ):
        raise serializers.ValidationError('You can only use your own uploaded images.')

    return value