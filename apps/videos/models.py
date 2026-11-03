from django.db import models
import uuid
from django.utils.text import slugify
from django.core.validators import MaxValueValidator

# Create your models here.
class Video(models.Model):

    class SourceType(models.TextChoices):
        UPLOAD = 'upload','Upload'
        EMBED = 'embed','Embed'
    class Status(models.TextChoices):
        DRAFT = 'draft','Draft'
        PENDING = 'pending','Pending Review'
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220,unique=True,blank=True)
    description = models.TextField()
    category = models.ForeignKey('categories.Category',on_delete=models.PROTECT,related_name='videos',null=True,blank=True)
    contributor = models.ForeignKey('accounts.User',on_delete=models.PROTECT,related_name='videos')
    source_type = models.CharField(max_length=20,choices=SourceType.choices)
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT)
    source_url = models.URLField(max_length=1000,blank=True)
    media_asset = models.ForeignKey('media_assets.Media_asset',on_delete=models.PROTECT,related_name='videos')
    thumbnail = models.ForeignKey('media_assets.Media_asset',on_delete=models.SET_NULL,related_name='video_thumbails',null=True,blank=True)
    duration = models.DecimalField(max_digits=5,decimal_places=2,null=True,blank=True,validators=[MaxValueValidator(60)])
    published_at = models.DateTimeField(null=True,blank=True)
    reviewed_by = models.ForeignKey('accounts.User',on_delete=models.SET_NULL,related_name='reviewed_videos',blank=True,null=True)
    reviewed_at = models.DateTimeField(blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'videos'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1

            while Video.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title