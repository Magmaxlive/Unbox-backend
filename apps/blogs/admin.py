from django.contrib import admin
from .models import Blog

# Register your models here.
@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'status', 'contributor']
    search_fields = ['content_title', 'note']
    ordering = ['-created_at']