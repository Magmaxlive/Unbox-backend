from django.db import models
import uuid
from django.utils.text import slugify
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
# Create your models here.


class EditorialQuerySet(models.QuerySet):
    def visible_to(self,user):
        if getattr(user,'role',None) == 'admin':
            return self.exclude(Q(status='draft') & ~Q(contributor=user))
        return self.filter(contributor=user)

class EditorialContent(models.Model):
    SLUG_FEEDBACK = 'content'
    objects = EditorialQuerySet.as_manager()

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

    def get_submission_errors(self):
        return {}


class ContentActivity(models.Model):
    class Action(models.TextChoices):
        CREATED = 'created','Created'
        EDITED = 'edited','Edited'
        SUBMITTED = 'submitted', 'Submitted for review'
        WITHDRAWN = 'withdrawn', 'Withdrawn'
        PUBLISHED = 'published', 'Published'
        REJECTED = 'rejected', 'Rejected'
        ARCHIVED = 'archived', 'Archived'
        RESTORED = 'restored', 'Restored'
        DELETED = 'deleted', 'Deleted'

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    content_type = models.ForeignKey(ContentType,on_delete=models.PROTECT)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type','object_id')
    content_title = models.CharField(max_length=300)
    actor = models.ForeignKey('accounts.User',on_delete=models.SET_NULL,related_name='content_activities',null=True,blank=True)
    action = models.CharField(max_length=20,choices=Action.choices)
    from_status = models.CharField(max_length=20,blank=True)
    to_status = models.CharField(max_length=20,blank=True)
    note = models.TextField(blank=True)
    changed_fields = models.JSONField(default=list,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'content_activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['content_type','object_id','-created_at'],
                name='content_activity_target_idx',
            )
        ]

    def __str__(self):
        return f'{self.get_action_display()} : {self.content_title}'

    @classmethod
    def record(cls,content,actor,action,from_status='',to_status='',note='',changed_fields=None):
        return cls.objects.create(
            content_type = ContentType.objects.get_for_model(content),
            object_id = content.pk,
            content_title = content.title,
            actor=actor,
            action=action,
            from_status=from_status,
            to_status=to_status,
            note=note,
            changed_fields=changed_fields or [],
        )

    @classmethod
    def for_content(cls,content):
        return cls.objects.filter(
            content_type = ContentType.objects.get_for_model(content),
            object_id = content.pk,
        ).select_related('actor')