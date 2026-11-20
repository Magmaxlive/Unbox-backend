from rest_framework import serializers
from .models import ContentActivity
from apps.categories.models import Category

class ContentActivitySerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source='get_action_display',read_only=True)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = ContentActivity
        fields = ['id','action','action_label','actor','actor_name','from_status','to_status','note','changed_fields','created_at']
        read_only_fields = fields

    def get_actor_name(self,obj):
        return obj.actor.name if obj.actor else None


class LockedRequiredFieldsMixin:
    """
    Once content has passed the submission checks (pending, published or
    archived), its required fields may be replaced but not removed.

    Subclasses set:
        LOCKED_REQUIRED_FIELDS = {'field_name': ('label', 'verb')}
    e.g. {'cover_image': ('cover image', 'replaced')}
    """
    LOCKED_REQUIRED_FIELDS = {}
    LOCKED_STATUSES = ('pending','published','achieved')

    def validate(self,attrs):
        attrs = super().validate(attrs)
        instance = getattr(self,'instance',None)

        if instance is not None and instance.status in self.LOCKED_STATUSES:
            status_label = instance.get_status_display().lower()
            content_label = instance._meta.verbose_name
            errors = {}

            for field, (label, verb) in self.LOCKED_REQUIRED_FIELDS.items():
                removing = field in attrs and attrs[field] is None
                if removing and getattr(instance, f'{field}_id'):
                    errors[field] = (
                        f"A {status_label} {content_label}'s {label} can be {verb} but not removed."
                    )

            if errors:
                raise serializers.ValidationError(errors)

        return attrs


class BulkActionSerializer(serializers.Serializer):
    """Input for bulk actions: up to 50 ids, duplicates removed (order kept)."""
    ids = serializers.ListField(
        child = serializers.UUIDField(),
        allow_empty=False,
        max_length=50
    )

    def validate_ids(self,value):
        return list(dict.fromkeys(value))


class BulkCategorySerializer(BulkActionSerializer):
    """Input for bulk category change: ids + an active destination category."""
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())

    def validate_category(self,value):
        if not value.is_active:
            raise serializers.ValidationError('Choose an active category.')
        return value
