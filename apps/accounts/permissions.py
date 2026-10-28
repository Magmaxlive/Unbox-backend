from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

def enforce_csrf(request):
    middleware = CSRFCheck(lambda request:None)
    reason = middleware.process_view(request,None,(),{})

    if reason:
        raise PermissionDenied(f"CSRF Failed : {reason}")


class IsAdminRole(BasePermission):
    message = 'Admin acccess required'

    def has_permission(self, request, view):
        user = request.user

        return (
            user
            and user.is_authenticated
            and user.role == 'admin'
        )


