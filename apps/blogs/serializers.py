from rest_framework import serializers
from .models import Blog
from apps.media_assets.models import Media_asset
from apps.categories.serializers import CategorySummarySerializer

class BlogSerializer(serializers.ModelSerializer):
    category_detail = CategorySummarySerializer(source='category',read_only=True)
    contributor_name = serializers.CharField(source='contributor.name',read_only=True)
    class Meta:
        model = Blog
        fields = ['id','contributor','contributor_name','category','category_detail','title','slug','content','excerpt','cover_image','status','reviewed_by','reviewed_at','rejection_reason','published_at','created_at','updated_at']
        read_only_fields =['id','contributor','contributor_name','category_detail','slug','reviewed_by','status','reviewed_at','rejection_reason','published_at','created_at','updated_at']

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