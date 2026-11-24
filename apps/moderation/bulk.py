"""
Bulk actions for editorial content (admin-only). Every item goes through
the same rules and logging as a single action; each item is its own
transaction, so results can be partial and are reported per item.
"""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import ContentActivity, EditorialContent
from .rules import get_edit_denial, is_author
from .services import perform_transition
from .rules import get_delete_denial, get_edit_denial, is_author

Status = EditorialContent.Status


def _error_text(error):
    """First readable message from a DRF exception (str, list or dict detail)."""
    detail = error.detail
    if isinstance(detail, dict):
        detail = next(iter(detail.values()), '')
    if isinstance(detail, list):
        detail = detail[0] if detail else ''
    return str(detail) or 'This item could not be changed.'


def _load_visible(model, user, ids):
    """Items this user can see, keyed by id (others' drafts are never included)."""
    return {obj.pk: obj for obj in model.objects.visible_to(user).filter(pk__in=ids)}


def bulk_transition(model, user, ids, transition):
    """Archive or restore many items. Returns {"succeeded": [...], "skipped": [...]}."""
    items = _load_visible(model, user, ids)
    succeeded, skipped = [], []

    for pk in ids:
        obj = items.get(pk)
        if obj is None:
            skipped.append({'id': str(pk), 'title': '', 'reason': 'Not found.'})
            continue

        try:
            perform_transition(obj, user, transition)
        except (PermissionDenied, ValidationError) as error:
            skipped.append({'id': str(pk), 'title': obj.title, 'reason': _error_text(error)})
            continue

        succeeded.append(str(pk))

    return {'succeeded': succeeded, 'skipped': skipped}


def bulk_change_category(model, user, ids, category):
    """
    Move many items to `category`, using the normal edit rules per item.
    Drafts are included for their author only (others' drafts are never
    visible); e.g. contributors: own drafts + rejected; admins: own drafts
    plus anyone's pending, published or archived.
    """
    items = _load_visible(model, user, ids)
    succeeded, skipped = [], []

    for pk in ids:
        obj = items.get(pk)
        if obj is None:
            skipped.append({'id': str(pk), 'title': '', 'reason': 'Not found.'})
            continue

        with transaction.atomic():
            # re-read under a lock so the checks use the latest state
            locked = type(obj).objects.select_for_update().select_related('category').get(pk=pk)

            if locked.category_id == category.pk:
                reason = 'Already in this category.'
            else:
                reason = get_edit_denial(user, locked)

            if reason:
                skipped.append({'id': str(pk), 'title': locked.title, 'reason': reason})
                continue

            old_name = locked.category.name if locked.category else 'no category'
            locked.category = category
            locked.save(update_fields=['category', 'updated_at'])

            # same logging rule as single edits: only when the editor isn't the author
            if not is_author(user, locked):
                ContentActivity.record(
                    locked,
                    user,
                    ContentActivity.Action.EDITED,
                    changed_fields=['category'],
                    note=f'Moved from {old_name} to {category.name}.',
                )

        succeeded.append(str(pk))

    return {'succeeded': succeeded, 'skipped': skipped}


def bulk_delete(model, user, ids):
    """
    Permanently delete many items, using the normal delete rules per item.
    Drafts are included for their author only; e.g. contributors: own drafts
    + rejected; admins: own drafts plus anyone's rejected or archived.
    """
    items = _load_visible(model, user, ids)
    succeeded, skipped = [], []

    for pk in ids:
        obj = items.get(pk)
        if obj is None:
            skipped.append({'id': str(pk), 'title': '', 'reason': 'Not found.'})
            continue

        with transaction.atomic():
            # re-read under a lock so the checks use the latest state
            locked = type(obj).objects.select_for_update().get(pk=pk)

            reason = get_delete_denial(user, locked)
            if reason:
                skipped.append({'id': str(pk), 'title': locked.title, 'reason': reason})
                continue

            # record first: after delete() the id/title/status are gone
            ContentActivity.record(
                locked,
                user,
                ContentActivity.Action.DELETED,
                from_status=locked.status,
            )
            locked.delete()

        succeeded.append(str(pk))

    return {'succeeded': succeeded, 'skipped': skipped}