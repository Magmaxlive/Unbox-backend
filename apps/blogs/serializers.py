from rest_framework import serializers
from .models import Blog
from apps.media_assets.models import Media_asset

class BlogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = ['id','contributor','category','title','slug','content','excerpt','cover_image','status','reviewed_by','reviewed_at','rejection_reason','published_at','created_at','updated_at']
        read_only_fields =['id','contributor','slug','reviewed_by','status','reviewed_at','rejection_reason','published_at','created_at','updated_at']

    def validate_cover_image(self,value):
        if value:
            if value.media_type != Media_asset.MediaType.IMAGE:
                raise serializers.ValidationError(
                    'Cover image must be an image'
                )

            if value.status != Media_asset.Status.READY:
                raise serializers.ValidationError(
                    'Cover image is not ready for use'
                )

            request = self.context.get('request')

            if ( request and not request.user.is_staff and value.uploaded_by_id != request.user.id):
                raise serializers.ValidationError(
                    'You can only use your own uploaded images'
                )

        return value