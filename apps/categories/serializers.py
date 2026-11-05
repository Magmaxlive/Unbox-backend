from rest_framework import serializers
from .models import *
import re


class Category_serializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.name',read_only=True)
    class Meta:
        model = Category
        fields = ['id','name','slug','color_name','color_hex','text_color_hex','created_by','created_at','description','updated_at','is_active','created_by_name',]
        read_only_fields = ['id','created_by','created_at','updated_at','created_by_name',]

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