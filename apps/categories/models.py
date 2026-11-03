from django.db import models
import uuid
from django.utils.text import slugify




class Category(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    name = models.CharField(max_length=200,unique=True)
    slug = models.SlugField(max_length=120,unique=True,blank=True)
    description = models.TextField(blank=True)
    color_name = models.CharField(max_length=50,blank=True)
    color_hex = models.CharField(max_length=7,default="#6A2FFC")
    text_color_hex = models.CharField(max_length=7,default='#FFFFFF')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('accounts.User',on_delete=models.PROTECT,related_name='created_categories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'categories'
        ordering = ['name']
        verbose_name_plural ='Categories'

    def save(self,*args,**kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug  
        super().save(*args,**kwargs)

    def __str__(self):
        return self.name