from django.core.validators import MaxValueValidator
from django.db import models

from apps.moderation.models import EditorialContent


class Video(EditorialContent):
    SLUG_FALLBACK = 'video'

    class SourceType(models.TextChoices):
        UPLOAD = 'upload', 'Upload'
        EMBED = 'embed', 'Embed'

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()  # plain text

    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    # embed: required (validated in the serializer)
    source_url = models.URLField(max_length=1000, blank=True)
    # upload: required (validated in the serializer); empty for embeds
    media_asset = models.ForeignKey(
        'media_assets.Media_asset',
        on_delete=models.PROTECT,
        related_name='videos',
        null=True,
        blank=True,
    )
    thumbnail = models.ForeignKey(
        'media_assets.Media_asset',
        on_delete=models.SET_NULL,
        related_name='video_thumbnails',
        null=True,
        blank=True,
    )
    # seconds; Unbox currently accepts short-form video only (max 60s)
    duration = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MaxValueValidator(60)],
    )

    class Meta:
        db_table = 'videos'
        ordering = ['-created_at']

    def __str__(self):
        return self.title