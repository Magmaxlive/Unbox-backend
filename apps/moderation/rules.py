from .models import EditorialContent

Status = EditorialContent.Status

def is_admin(user):
    return getattr(user,'role',None) == 'admin'

def is_author(user,content):
    return content.contributor_id == user.id

def get_view_denial(user,content):
    if is_author(user,content):
        return None

    if not is_admin(user):
        return 'You do not have permission to access this content.'

    if content.status == Status.DRAFT:
        return "Draft are only visible to their author"

    return None


def get_edit_denial(user,content):
    status = content.status

    if is_author(user,content):
        # admin can edit their own content in any status
        if is_admin(user) or status in (Status.DRAFT or Status.REJECTED):
            return None

        if status == Status.PENDING:
            return 'This content is penind reivew. Withdraw it from review before editing.'

        return 'Published or archieved content can only be changed by admin. Contact an admin if changes are needed.'

    if not is_admin(user):
        return 'You do not have permission to edit this content'

    # admin editing someone else's content
    if status in (Status.PENDING,Status.PUBLISHED,Status.ARCHIVED):
        return None

    if status == Status.REJECTED:
        return 'Rejected content is back with its author for changes.'

    return 'Drafts can only be edited by their author'


def get_delete_denial(user,content):
    status = content.status

    if is_author(user,content):
        allowed = (Status.DRAFT, Status.REJECTED, Status.ARCHIVED) if is_admin(user) \
            else (Status.DRAFT, Status.REJECTED)

        if status in allowed:
            return None

        if status == Status.PENDING:
            return 'This content is pending reveiw. Withdraw it form review before deleting.'

        if status == Status.PUBLISHED and is_admin(user):
            return "Published content must be archieved before it can be deleted."

        return 'Published or archieved content can only be removed by admin . Contact an admin if needed'

    if not is_admin(user):
        return "You do not have permission to delete this content."

    # admin deleting someone else content
    if status in (Status.REJECTED,Status.ARCHIVED):
        return None

    if status == Status.PUBLISHED:
        return "Published content must be archieved before it can be deleted."

    if status == Status.PENDING:
        return "Pending content cannot be deleted . Reject it instead if it should not be published ."

    return "Drafts can only be deleted by its author"

def get_transition_denial(user,content,transition):
    status = content.status
    author = is_author(user,content)
    admin = is_admin(user)

    if transition == 'submit':
        if not author:
            return 'Only the author can submit this content for review.'
        if status not in (Status.DRAFT,Status.REJECTED):
            return 'Only draft or rejected content can be submitted for review.'
        return None

    if transition == 'withdraw':
        if not author:
            return 'Only the author can withdraw this content from review.'
        if status != Status.PENDING:
            return 'Only content pending review can be withdrawn.'
        return None

    if transition == 'publish':
        if not admin:
            return 'Only admins can publish content .'
        allowed = (Status.DRAFT,Status.PENDING) if author else (Status.PENDING)

        if status in allowed:
            return None

        if status == Status.REJECTED:
            return 'Rejected content must be resubmitted by its author before it can be published.'

        if status == Status.ARCHIVED:
            return 'Archieved content must be restored, not published .'

        if status == Status.PUBLISHED:
            return 'This content is already published .'

        return 'Drafts must be submitted by their author before they can be published .'

    if transition == 'reject':
        if not admin:
            return 'Only admins can reject content'
        if status != Status.PENDING:
            return 'Only content pending review can be rejected .'
        return None

    if transition == 'archive':
        if not admin:
            return 'Only admins can archive content.'
        if status != Status.PUBLISHED:
            return 'Only published content can be archieved.'
        return None

    if transition == 'restore':
        if not admin:
            return 'Only admins can restore content.'
        if status != Status.ARCHIVED:
            return 'Only archived content can be restored .'
        return None

    return 'Unknown action .'