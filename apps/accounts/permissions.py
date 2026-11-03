from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission,SAFE_METHODS

def enforce_csrf(request):
    middleware = CSRFCheck(lambda request:None)
    reason = middleware.process_view(request,None,(),{})

    if reason:
        raise PermissionDenied(f"CSRF Failed : {reason}")


class IsAdminRole(BasePermission):
    message = 'Admin acccess required'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == 'admin'
        )


class IsContributorRole(BasePermission):
    message = 'Contributor access required'

    def has_permission(self, request, view):
        user = request.user
        return (
            request.user.is_authenticated
            and request.user.role == 'contributor'
        )
    

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):

        if not request.user or not request.user.is_authenticated :
            return False
        
        if request.method in SAFE_METHODS:
            return True
        
        return request.user.role == 'admin'


class IsOwnerOrAdmin(BasePermission):
    message = "You do not have permission to perform this action."
    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.role == 'admin':
            if request.method == 'DELETE':
                if obj.status not in [
                    obj.Status.DRAFT,
                    obj.Status.REJECTED,
                ]:
                    self.message = "Only draft or rejected content can be deleted."
                    return False
            return True

        if obj.contributor_id != user.id:
            self.message = 'You do not have permission to access this content.'
            return False
        
        if request.method in SAFE_METHODS:
            return True
        
        if obj.status not in [
                obj.Status.DRAFT,
                obj.Status.REJECTED,
            ]:
            self.message = 'You can only edit or delete draft or rejected content.'
            return False
        return True