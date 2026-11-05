from django.db import models
import uuid
from django.utils.text import slugify

class Blog(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft','Draft'
        PENDING = 'pending','Pending Review'
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    contributor = models.ForeignKey('accounts.User',on_delete=models.PROTECT,related_name='blogs')
    category = models.ForeignKey('categories.Category',on_delete=models.PROTECT,related_name='blogs',blank=True,null=True)
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300,blank=True,unique=True)
    content = models.TextField()
    excerpt = models.CharField(max_length=300,blank=True)
    cover_image = models.ForeignKey('media_assets.Media_asset',on_delete=models.SET_NULL,related_name='blog_cover_image',null=True,blank=True)
    status = models.CharField(max_length=50,choices=Status.choices,default=Status.DRAFT)
    reviewed_by = models.ForeignKey('accounts.User',on_delete=models.SET_NULL,related_name='reviewed_blogs',null=True,blank=True)
    reviewed_at = models.DateTimeField(blank=True,null=True)
    rejection_reason = models.TextField(blank=True)
    published_at = models.DateTimeField(blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'blogs'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or "blog"
            slug = base_slug
            counter = 1

            while Blog.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
