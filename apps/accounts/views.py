from django.shortcuts import render
from rest_framework import generics,permissions,status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken,TokenError
from .serializers import *
from django.conf import settings
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

# Create your views here.
class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access_token = serializer.validated_data['access']
        refresh_token = serializer.validated_data['refresh']

        response = Response(
            {'message':'Login successfull'},
            status=status.HTTP_200_OK,
        )

        secure = not settings.DEBUG

        response.set_cookie(
            key='access_token',
            value=access_token,
            httponly=True,
            secure=secure,
            samesite='Lax',
            path='/',
            max_age=15*60
        )

        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            httponly=True,
            secure=secure,
            samesite='Lax',
            path='/api/v1/auth/',
            max_age=7 * 24 * 60 * 60,
        )
        return response

class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class CookieTokenRefreshView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self,request):
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response(
                {'detail' : 'Refresh Token missing'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = TokenRefreshSerializer(
            data = {'refresh':refresh_token}
        )

        try:
            serializer.is_valid(raise_exception=True)

        except (InvalidToken,TokenError):
            response = Response (
                {'error':'Invalid refresh token or expired'},
                status=status.HTTP_401_UNAUTHORIZED
                )
            
            response.delete_cookie(
                'access_token',
                path='/',
                samesite='Lax'
            )

            response.delete_cookie(
                'refresh_token',
                path='/api/v1/auth/',
                samesite='Lax'
            )

            return response

        tokens = serializer.validated_data

        response = Response(
            {'message':'Token refreshed successfully'},
            status=status.HTTP_200_OK
        )

        response.set_cookie(
            key="access_token",
            value=tokens["access"],
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax",
            path="/",
            max_age=15 * 60,
        )

        if "refresh" in tokens:
            response.set_cookie(
                key="refresh_token",
                value=tokens["refresh"],
                httponly=True,
                secure=not settings.DEBUG,
                samesite="Lax",
                path="/api/v1/auth/",
                max_age=7 * 24 * 60 * 60,
            )

        return response


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self,request):
        refresh_token = request.COOKIES.get('refresh_token')

        response = Response(
            {'message':'Logged out Successfully'},
            status=status.HTTP_200_OK,
        )

        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except(InvalidToken,TokenError) :
                pass

        response.delete_cookie(
            'access_token',
            path='/',
            samesite='Lax'
        )

        response.delete_cookie(
            'refresh_token',
            path='/api/v1/auth/',
            samesite='Lax'
        )

        return response