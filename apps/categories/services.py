from django.db import transaction

from apps.moderation.models import ContentActivity,EditorialContent
from apps.moderation.rules import is_author

Status = EditorialContent.Status

CONTENT_RELATIONS = ('blogs','videos')

def move_category_content(source,target,user,deactivate_source=False):
    """
    Move all non-draft content from `source` to `target` (a category merge).
    Drafts stay with their authors and are counted in `drafts_left`.
    All or nothing: runs in one transaction.
    """

    moved = {}
    drafts_left = {}

    with transaction.atomic():
        for relation in CONTENT_RELATIONS:
            items = getattr(source,relation).select_for_update().exclude(status=Status.DRAFT)

            count = 0
            for item in items:
                item.category = target
                item.save(update_fields=['category','updated_at'])

            # same logging rule as edits: only when the editor isn't the author
                if not is_author(user,item):
                    ContentActivity.record(
                        item,
                        user,
                        ContentActivity.Action.EDITED,
                        changed_fields=['category'],
                        note=f"Moved from {source.name} to {target.name} .",
                    )
                count +=1

            moved[relation] = count
            drafts_left[relation] = getattr(source,relation).filter(status=Status.DRAFT).count()


        deactivated = False
        if deactivate_source and source.is_active:
            source.is_active = False
            source.save(update_fields=['is_active','updated_at'])
            deactivated = True

        return {
            'moved':moved,
            'drafts_left':drafts_left,
            'deactivated':deactivated
        }