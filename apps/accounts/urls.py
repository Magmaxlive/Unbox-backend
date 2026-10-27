from django.urls import path,include
from .views import *

urlpatterns = [
    path('login/',LoginView.as_view(),name='login'),
    path('me/',CurrentUserView.as_view(),name='current_user')
]
