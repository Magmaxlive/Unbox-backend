from django.db import models
import uuid
from django.utils.text import slugify

# Create your models here.

class EditorialContent(models.Model):
    SLUG_FEEDBACK = 'content'

    class Status(models.TextChoices):
        DRAFT = 'draft','Draft'
        PENDING = 'pending','Pending Review'
        PUBLISHED = 'published', 'Published'
        REJECTED = 'rejected', 'Rejected'
        ARCHIVED = 'archived', 'Archived'

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    contributor = models.ForeignKey('accounts.User',on_delete=models.PROTECT,related_name='%(class)ss')
    category = models.ForeignKey('categories.Category',on_delete=models.PROTECT,related_name='%(class)ss',null=True,blank=True)
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True,blank=True)
    reviewed_by = models.ForeignKey('accounts.User',on_delete=models.SET_NULL,related_name='reviewed_%(class)ss',null=True,blank=True)
    reviewed_at = models.DateTimeField(null=True,blank=True)
    rejection_reason = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def _generate_unique_slug(self):
        max_length = self._meta.get_field('slug').max_length
        base_slug = slugify(self.title) or self.SLUG_FALLBACK
        base_slug = base_slug[:max_length]

        slug = base_slug
        counter = 1
        manager = type(self)._default_manager

        while manager.filter(slug=slug).exclude(pk=self.pk).exists():
            suffix = f'-{counter}'
            # trim the base so base + suffix always fits the field
            slug = f'{base_slug[:max_length - len(suffix)]}{suffix}'
            counter += 1

        return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)
