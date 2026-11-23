from rest_framework import serializers
from .models import Video
from apps.moderation.serializers import LockedRequiredFieldsMixin
from apps.media_assets.serializers import MediaImageSummarySerializer
from apps.media_assets.validators import validate_image_asset
from apps.categories.serializers import CategorySummarySerializer
from .embeds import EmbedError,build_player_url,parse_embed_url,verify_embed

class VideoSerializer(LockedRequiredFieldsMixin,serializers.ModelSerializer):
    category_detail = CategorySummarySerializer(source = 'category',read_only=True)
    contributor_name = serializers.CharField(source = 'contributor.name',read_only=True)
    thumbnail_detail = MediaImageSummarySerializer(source = 'thumbnail',read_only=True)

    description = serializers.CharField(max_length=5000,allow_blank=True,required=False)
    source_url = serializers.CharField(max_length=1000,allow_blank=True,required=False)
    player_url = serializers.SerializerMethodField()

    LOCKED_REQUIRED_FIELDS = {
        'category':('category','changed'),
        'thumbnail':('thumbnail','replaced'),
        'source_url':('link','replaced')
    }

    class Meta:
        model = Video
        fields = [
            'id',
            'contributor',
            'contributor_name',
            'category',
            'category_detail',
            'title',
            'slug',
            'description',
            'source_type',
            'source_url',
            'provider',
            'external_id',
            'media_asset',
            'thumbnail',
            'thumbnail_detail',
            'duration',
            'status',
            'submitted_at',
            'reviewed_by',
            'reviewed_at',
            'rejection_reason',
            'published_at',
            'created_at',
            'updated_at',
            'player_url'

        ]

        read_only_fields = [
            'id',
            'contributor',
            'contributor_name',
            'category_detail',
            'thumbnail_detail',
            'slug',
            'player_url',
            # set by later steps, never by clients:
            'provider',      # V2: parsed from source_url
            'external_id',   # V2: parsed from source_url
            'media_asset',   # V3: attached by the upload flow
            'duration',      # V4: copied from processing
            'status',
            'submitted_at',
            'reviewed_by',
            'reviewed_at',
            'rejection_reason',
            'published_at',
            'created_at',
            'updated_at',
        ]

    def validate_description(self, value):
        return value.strip()

    def validate_thumbnail(self,value):
        return validate_image_asset(value,self.context.get('request'),label='thumbnail')

    def validate_source_type(self, value):
        if self.instance is not None and value != self.instance.source_type:
            raise serializers.ValidationError(
                "The video type can't be changed after it's created. Create a new video instead."
            )
        return value


    def get_player_url(self,obj):
        if obj.source_type != Video.SourceType.EMBED:
            return ''
        return build_player_url(obj.provider,obj.external_id)

    def validate(self, attrs):
        # the mixin runs first: a submitted video's link can't be removed
        attrs = super().validate(attrs)
        instance = self.instance

        source_type = attrs.get(
            'source_type',
            instance.source_type if instance else None,
        )

        if source_type == Video.SourceType.UPLOAD:
            if attrs.get('source_url'):
                raise serializers.ValidationError(
                    {'source_url': 'A link is only used for embedded videos.'}
                )
            return attrs

        if source_type == Video.SourceType.EMBED and 'source_url' in attrs:
            url = (attrs['source_url'] or '').strip()

            if not url:
                # removing the link from a draft or rejected video
                attrs['source_url'] = ''
                attrs['provider'] = ''
                attrs['external_id'] = ''
                return attrs

            # only check when the link actually changes
            if instance is None or url != instance.source_url:
                try:
                    parsed = parse_embed_url(url)
                    verify_embed(parsed)
                except EmbedError as error:
                    raise serializers.ValidationError({'source_url': str(error)})

                attrs['source_url'] = parsed.canonical_url
                attrs['provider'] = parsed.provider
                attrs['external_id'] = parsed.external_id

        return attrs