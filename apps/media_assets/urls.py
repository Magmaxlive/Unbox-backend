from django.urls import path

from .views import ImageUploadCompleteView, ImageUploadRequestView

urlpatterns = [
    path('uploads/', ImageUploadRequestView.as_view(), name='media-upload-request'),
    path('<uuid:id>/complete/', ImageUploadCompleteView.as_view(), name='media-upload-complete'),
]