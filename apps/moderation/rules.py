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