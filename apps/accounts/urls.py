from django.urls import path,include
from .views import *
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('login/',LoginView.as_view(),name='login'),
    path('me/',CurrentUserView.as_view(),name='current_user'),
    path('token/refresh/',CookieTokenRefreshView.as_view(),name='token_refresh'),
    path('logout/',LogoutView.as_view(),name='logout')

]
