from rest_framework.permissions import BasePermission,SAFE_METHODS
from .rules import get_delete_denial,get_edit_denial,get_view_denial

class EditorialContentPermission(BasePermission):
    message = 'You do not have permission to perform this action'

    def has_object_permission(self, request, view, obj):
        user = request.user

        denial = get_view_denial(user,obj)

        if denial is None and request.method not in SAFE_METHODS:
            if request.method in ('PUT','PATCH'):
                denial = get_edit_denial(user,obj)
            elif request.method == 'DELETE':
                denial = get_delete_denial(user,obj)
            else:
                denial = 'This action is not allowed here'

        if denial:
            # DRF returns this as {"detail": ...} with status 403
            self.message = denial
            return False
        
        return True