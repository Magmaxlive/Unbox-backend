from django.shortcuts import render
from rest_framework import generics,permissions
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView
from .serializers import *

# Create your views here.
class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

