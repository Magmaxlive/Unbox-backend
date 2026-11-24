from django.core.validators import MaxValueValidator
from django.db import models

from apps.moderation.models import EditorialContent


class Video(EditorialContent):
    SLUG_FALLBACK = 'video'
    MAX_DURATION_SECONDS = 60

    class SourceType(models.TextChoices):
        UPLOAD = 'upload', 'Upload'
        EMBED = 'embed', 'Embed'

    class Provider(models.TextChoices):
        YOUTUBE = 'youtube','YouTube'
        VIMEO = 'vimeo','Vimeo'
        TIKTOK = 'tiktok','TikTok'
        INSTAGRAM = 'instagram','Instagram'

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)  # plain text

    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    # embed: required (validated in the serializer)
    source_url = models.URLField(max_length=1000, blank=True)
    provider = models.CharField(max_length=20,choices=Provider.choices,blank=True)
    external_id = models.CharField(max_length=100,blank=True)

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


    def get_submission_errors(self):
        from apps.media_assets.models import Media_asset
        errors = {}

        if not self.category_id:
            errors['category'] = 'Choose a category before submitting.'

        if not self.thumbnail_id:
            errors['thumbnail'] = 'Add a thumbnail before submitting.'

        if not (self.description or '').strip():
            errors['description'] = 'Add a description before submitting.'

        if self.source_type == self.SourceType.UPLOAD:
            asset = self.media_asset

            if asset is None:
                errors['media_asset'] = 'Upload a video before submitting.'
            elif asset.status == Media_asset.Status.FAILED:
                errors['media_asset'] = 'The video upload failed. Please upload it again.'
            elif asset.status != Media_asset.Status.READY:
                errors['media_asset'] = 'The video is still processing. Please try again in a moment.'
            elif self.duration is not None and self.duration > self.MAX_DURATION_SECONDS:
                errors['media_asset'] = f'Videos must be {self.MAX_DURATION_SECONDS} seconds or shorter.'

        elif self.source_type == self.SourceType.EMBED:
            if not (self.provider and self.external_id):
                errors['source_url'] = 'Add a valid video link before submitting.'

        return errors


    def on_status_change(self,from_status,to_status):
            """Published videos have their files on the CDN; nothing else does."""
            from apps.media_assets.services import publish_video_files,unpublish_video_files
    
            if self.source_type != self.SourceType.UPLOAD or self.media_asset is None:
                return  #embed platform host the video
    
            if to_status == self.Status.PUBLISHED:
                publish_video_files(self.media_asset)
            elif from_status == self.Status.PUBLISHED:
                unpublish_video_files(self.media_asset)