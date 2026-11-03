from django.db import models
import uuid
from django.core.validators import MaxValueValidator


# Create your models here.
class Media_asset(models.Model):
    class MediaType(models.TextChoices):
        VIDEO = "video", "Video"
        IMAGE = "image", "Image"
        DOCUMENT = "document", "Document"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        UPLOADING = "uploading", "Uploading"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"


    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    uploaded_by = models.ForeignKey('accounts.User',on_delete=models.PROTECT,related_name='media_assets')
    bucket_name = models.CharField(max_length=200)
    storage_key = models.CharField(max_length=500,unique=True)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=100)
    media_type = models.CharField(max_length=50,choices=MediaType.choices)
    status = models.CharField(max_length=20,choices=Status.choices)
    width = models.PositiveIntegerField(null=True,blank=True)
    height = models.PositiveIntegerField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "media_assets"
        ordering = ["-created_at"]

    def __str__(self):
        return self.file_name