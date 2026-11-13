from django.contrib import admin
from .models import ContentActivity

# Register your models here.
@admin.register(ContentActivity)
class contentActivityAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'action', 'content_title', 'content_type', 'actor', 'from_status', 'to_status']
    list_filter = ['action', 'content_type']
    search_fields = ['content_title', 'note']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
