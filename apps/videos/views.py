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


RELATED = ('contributor','category','thumbnail','media_asset')

class VideoListCreateView(generics.ListCreateAPIView,EditorialActivityListView):
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

class VideoDetailView(EditorialActivityMixin,generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VideoSerializer
    lookup_field = 'id'
    permission_classes = [IsAuthenticated,EditorialContentPermission]

    def get_queryset(self):
        return Video.objects.visible_to(self.request.user).select_related(*RELATED)

class VideoTransitionView(EditorialTransitionView):
    model = Video
    serializer_class = VideoSerializer

class VideoActivityView(EditorialActivityListView):
    model = Video