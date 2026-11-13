from rest_framework import serializers
from .models import *
import re


class Category_serializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.name',read_only=True)
    blog_count = serializers.SerializerMethodField()
    video_count = serializers.SerializerMethodField()
    usage_count = serializers.SerializerMethodField()
    class Meta:
        model = Category
        fields = ['id','name','slug','color_name','color_hex','text_color_hex','created_by','created_at','description','updated_at','is_active','created_by_name','blog_count','video_count','usage_count']
        read_only_fields = ['id','created_by','created_at','updated_at','created_by_name','blog_count','video_count','usage_count']

    def _count(self,obj,annotation,related_name):
        annotated = getattr(obj,annotation,None)
        if annotated is not None:
            return annotated
        return getattr(obj,related_name).count()

    def get_blog_count(self,obj):
        return self._count(obj,'blog_count','blogs')

    def get_video_count(self,obj):
            return self._count(obj,'video_count','videos')

    def get_usage_count(self,obj):
            return self.get_blog_count(obj) + self.get_video_count(obj)

    def validate_color_hex(self, value):
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            raise serializers.ValidationError(
                "Enter a valid HEX color, e.g. #2676E5."
            )

        return value.upper()


    def validate_text_color_hex(self, value):
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            raise serializers.ValidationError(
                "Enter a valid HEX color, e.g. #FFFFFF."
            )

        return value.upper()

class CategorySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id','name','color_hex','text_color_hex']
        read_only_fields = fields