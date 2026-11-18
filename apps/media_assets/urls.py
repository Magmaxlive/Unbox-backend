from django.urls import path
from .views import *

urlpatterns = [
   path('uploads/',ImageUploadRequestView.as_view(),name='media-upload-request')
]