from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken,TokenError
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied

class CookieJWTAuthentication(JWTAuthentication):
    def enforce_csrf(self,request):
        check = CSRFCheck(lambda request:None)
        check.process_request(request)
        reason = check.process_view(request,None,(),{})

        if reason:
            raise PermissionDenied(f"CSRF Failed :{reason}")

    def authenticate(self, request):
        token = request.COOKIES.get('access_token')

        if not token:
            return None

        try:
            validated_token = self.get_validated_token(token)
            user = self.get_user(validated_token)
            return (user,validated_token)
        
        except(InvalidToken,TokenError):
            return None