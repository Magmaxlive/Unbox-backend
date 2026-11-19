from django.urls import path

from .views import ImageUploadCompleteView, ImageUploadRequestView,MediaAssetsListView,MediaAssetDetailView

urlpatterns = [
    path('',MediaAssetsListView.as_view(),name='media-list'),
    path('<uuid:id>/',MediaAssetDetailView.as_view(),name='media-detail'),
    path('uploads/', ImageUploadRequestView.as_view(), name='media-upload-request'),
    path('<uuid:id>/complete/', ImageUploadCompleteView.as_view(), name='media-upload-complete'),
]