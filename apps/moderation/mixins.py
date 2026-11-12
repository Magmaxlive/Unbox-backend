from django.db import transaction
from .models import ContentActivity
from .rules import is_author

Action = ContentActivity.Action

"""
    Names of fields whose incoming value differs from the stored value.
    Run BEFORE serializer.save(). Related objects compare by primary key
    (Django model equality), and content is compared after sanitising
    because validate_content has already cleaned validated_data.
    """

def get_changed_fields(instance,validated_data):
    return sorted(
        field for field, new_value in validated_data.items()
        if getattr(instance,field) != new_value 
    )

"""
    Adds activity logging to DRF generic views for editorial content.

    - create:  logs CREATED (author = current user)
    - update:  logs EDITED with changed_fields, only when the editor is
               not the author (authors' own edits are not logged)
    - destroy: logs DELETED before deleting, so the entry keeps the title
    """

class EditorialActivityMixin:
    def perform_create(self,serializer):
        user = self.request.user

        with transaction.atomic():
            instance = serializer.save(contributor = user)
            ContentActivity.record(
                instance,
                user,
                Action.CREATED,
                to_status=instance.status,
            )

    def perform_update(self,serializer):
        user = self.request.user
        changed_fields = get_changed_fields(serializer.instance, serializer.validated_data)

        with transaction.atomic():
            instance = serializer.save()

            if changed_fields and not is_author(user,instance):
                ContentActivity.record(
                    instance,user,Action.EDITED,changed_fields=changed_fields,
                )


    def perform_destroy(self,instance):
        user = self.request.user

        with transaction.atomic():
            ContentActivity.record(
                instance,
                user,
                Action.DELETED,
                from_status=instance.status
            )
            instance.delete()