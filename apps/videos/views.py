from django.shortcuts import render
from rest_framework import generics,filters
from apps.core.pagination import StandardResultsPagination
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from apps.moderation.mixins import EditorialActivityMixin
from apps.moderation.permissions import EditorialContentPermission
from apps.moderation.views import EditorialActivityListView,EditorialTransitionView
from .filters import VideoFilter
from .serializers import VideoSerializer
from .models import Video 
from apps.media_assets.services import refresh_video_processing


RELATED = ('contributor','category','thumbnail','media_asset')

def _refresh_processing(video):
    """Update a processing upload's status (throttled) before it's shown."""
    asset = video.media_asset
    if asset is None:
        return
    refresh_video_processing(asset)
    if asset.status == asset.Status.READY:
        video.duration = asset.duration

class VideoListCreateView(EditorialActivityMixin,generics.ListCreateAPIView):
    serializer_class = VideoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = VideoFilter
    search_fields = ['title','contributor__name']
    ordering_fields = ['created_at', 'updated_at', 'published_at']

    def get_queryset(self):
        query = Video.objects.visible_to(self.request.user).select_related(*RELATED).order_by('-created_at')
        return query

    def paginate_queryset(self, queryset):
        page = super().paginate_queryset(queryset)
        for video in page or []:
            _refresh_processing(video)
        return page

class VideoDetailView(EditorialActivityMixin,generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VideoSerializer
    lookup_field = 'id'
    permission_classes = [IsAuthenticated,EditorialContentPermission]

    def get_queryset(self):
        return Video.objects.visible_to(self.request.user).select_related(*RELATED)

    def get_object(self):
        video = super().get_object()
        if self.request.method == 'GET':
            _refresh_processing(video)
        return video

class VideoTransitionView(EditorialTransitionView):
    model = Video
    serializer_class = VideoSerializer

class VideoActivityView(EditorialActivityListView):
    model = Video