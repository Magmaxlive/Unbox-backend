from rest_framework import serializers
from .models import *
import re


class Category_serializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id','name','slug','color_name','color_hex','text_color_hex','created_by','created_at','description','updated_at','is_active']
        read_only_fields = ['id','slug','created_by','created_at','updated_at']

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

    @staticmethod
    def get_luminance(hex_color):
        hex_color = hex_color.lstrip("#")

        rgb = [
            int(hex_color[i:i + 2], 16) / 255
            for i in (0, 2, 4)
        ]

        def linearize(channel):
            if channel <= 0.04045:
                return channel / 12.92

            return ((channel + 0.055) / 1.055) ** 2.4

        r, g, b = map(linearize, rgb)

        return (
            0.2126 * r
            + 0.7152 * g
            + 0.0722 * b
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # Support PATCH: use submitted values or existing instance values.
        background = attrs.get(
            "color_hex",
            getattr(self.instance, "color_hex", "#6A2FFC")
        )

        text_color = attrs.get(
            "text_color_hex",
            getattr(self.instance, "text_color_hex", "#FFFFFF")
        )

        bg_lum = self.get_luminance(background)
        text_lum = self.get_luminance(text_color)

        lighter = max(bg_lum, text_lum)
        darker = min(bg_lum, text_lum)

        contrast_ratio = (lighter + 0.05) / (darker + 0.05)

        if contrast_ratio < 4.5:
            raise serializers.ValidationError({
                "text_color_hex": (
                    f"Insufficient contrast ({contrast_ratio:.2f}:1). "
                    "Choose colors with a contrast ratio of at least 4.5:1."
                )
            })

        return attrs