from django.urls import path

from .views import *

urlpatterns = [
    path('',MediaAssetsListView.as_view(),name='media-list'),
    path('<uuid:id>/',MediaAssetDetailView.as_view(),name='media-detail'),
    path('uploads/', ImageUploadRequestView.as_view(), name='media-upload-request'),
    path('<uuid:id>/complete/', ImageUploadCompleteView.as_view(), name='media-upload-complete'),

        # videos: multipart uploads
    path('video-uploads/', VideoUploadStartView.as_view(), name='media-video-upload-start'),
    path('<uuid:id>/video/parts/', VideoUploadPartsView.as_view(), name='media-video-upload-parts'),
    path('<uuid:id>/video/complete/', VideoUploadCompleteView.as_view(), name='media-video-upload-complete'),
    path('<uuid:id>/video/abort/', VideoUploadAbortView.as_view(), name='media-video-upload-abort'),
]