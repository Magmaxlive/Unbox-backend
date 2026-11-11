from django.db import models
from apps.core.sanitize import rich_text_is_empty
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

    def get_submission_errors(self):
        errors = {}

        if not self.category_id:
            errors['category'] = 'Choose a category before submitting'

        if rich_text_is_empty(self.content):
            errors['content'] = 'Content cannot be empty'
        return errors

    def __str__(self):
        return self.title