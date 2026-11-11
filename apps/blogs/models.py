from django.db import models

from apps.moderation.models import EditorialContent


class Blog(EditorialContent):
    SLUG_FALLBACK = 'blog'

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, blank=True, unique=True)
    content = models.TextField()
    excerpt = models.CharField(max_length=300, blank=True)
    cover_image = models.ForeignKey(
        'media_assets.Media_asset',
        on_delete=models.SET_NULL,
        related_name='blog_cover_image',
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'blogs'
        ordering = ['-created_at']

    def __str__(self):
        return self.title