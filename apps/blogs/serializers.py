from rest_framework import serializers
from .models import Blog
from apps.media_assets.models import Media_asset
from apps.categories.serializers import CategorySummarySerializer
from apps.core.sanitize import sanitize_rich_text,rich_text_is_empty
from apps.media_assets.serializers import MediaImageSummarySerializer
from apps.media_assets.validators import validate_image_asset
from apps.moderation.serializers import LockedRequiredFieldsMixin

class BlogSerializer(LockedRequiredFieldsMixin,serializers.ModelSerializer):
    category_detail = CategorySummarySerializer(source='category',read_only=True)
    cover_image_detail = MediaImageSummarySerializer(source='cover_image',read_only=True)
    contributor_name = serializers.CharField(source='contributor.name',read_only=True)

    LOCKED_REQUIRED_FIELDS = {
        'category' : ('category','changed'),
        'cover_image' : ('cover_image','replaced')
    }
    class Meta:
        model = Blog
        fields = ['id','contributor','contributor_name','category','category_detail','title','slug','content','excerpt','cover_image','cover_image_detail','status','reviewed_by','reviewed_at','rejection_reason','published_at','created_at','updated_at']
        read_only_fields =['id','contributor','contributor_name','category_detail','slug','reviewed_by','status','reviewed_at','cover_image_detail','rejection_reason','published_at','created_at','updated_at']


    def validate_content(self,value):
        cleaned = sanitize_rich_text(value)

        if rich_text_is_empty(cleaned):
            raise serializers.ValidationError('Content cannot be empty.')

        return cleaned

    def validate_cover_image(self,value):
        return validate_image_asset(value, self.context.get('request'),label='Cover image')