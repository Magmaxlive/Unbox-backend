from django.shortcuts import render
from rest_framework import generics,permissions,status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView
from .serializers import *
from django.conf import settings

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

