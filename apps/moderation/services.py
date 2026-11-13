from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import ContentActivity, EditorialContent
from .rules import get_transition_denial

Status = EditorialContent.Status
Action = ContentActivity.Action

# transition -> (target status, activity action)
TRANSITIONS = {
    'submit': (Status.PENDING, Action.SUBMITTED),
    'withdraw': (Status.DRAFT, Action.WITHDRAWN),
    'publish': (Status.PUBLISHED, Action.PUBLISHED),
    'reject': (Status.REJECTED, Action.REJECTED),
    'archive': (Status.ARCHIVED, Action.ARCHIVED),
    'restore': (Status.PUBLISHED, Action.RESTORED),
}


def perform_transition(content, user, transition, reason=''):
    """
    The only code path that changes an editorial content's status.
    Locks the row, checks rules, validates completeness, updates tracking
    fields, and logs the activity, all in one transaction.
    """
    if transition not in TRANSITIONS:
        raise ValidationError({'detail': 'Unknown action.'})

    target_status, activity_action = TRANSITIONS[transition]
    reason = (reason or '').strip()

    with transaction.atomic():
        # Re-read under a row lock so concurrent actions see the latest status.
        locked = type(content).objects.select_for_update().get(pk=content.pk)

        denial = get_transition_denial(user, locked, transition)
        if denial:
            raise PermissionDenied(denial)

        if transition in ('submit', 'publish'):
            errors = locked.get_submission_errors()
            if errors:
                raise ValidationError(errors)

        if transition == 'reject' and not reason:
            raise ValidationError({'reason': 'A reason is required when rejecting content.'})

        from_status = locked.status
        now = timezone.now()
        update_fields = ['status', 'updated_at']

        if transition == 'submit':
            locked.submitted_at = now
            locked.rejection_reason = ''  # previous reason is kept in the activity log
            update_fields += ['submitted_at', 'rejection_reason']

        elif transition == 'withdraw':
            locked.submitted_at = None
            update_fields += ['submitted_at']

        elif transition == 'publish':
            locked.reviewed_by = user
            locked.reviewed_at = now
            locked.rejection_reason = ''
            update_fields += ['reviewed_by', 'reviewed_at', 'rejection_reason']
            if locked.published_at is None:
                # first publish only; restore keeps the original date
                locked.published_at = now
                update_fields.append('published_at')

        elif transition == 'reject':
            locked.reviewed_by = user
            locked.reviewed_at = now
            locked.rejection_reason = reason
            update_fields += ['reviewed_by', 'reviewed_at', 'rejection_reason']

        # archive / restore: status change only

        locked.status = target_status
        locked.save(update_fields=update_fields)

        ContentActivity.record(
            locked,
            user,
            activity_action,
            from_status=from_status,
            to_status=target_status,
            note=reason if transition == 'reject' else '',
        )

        # Phase 3: transaction.on_commit(lambda: notify_transition(locked, user, transition))

    return locked