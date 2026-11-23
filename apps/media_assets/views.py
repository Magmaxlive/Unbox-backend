from django.shortcuts import get_object_or_404
from rest_framework import status,filters,generics
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.conf import settings


from rest_framework.views import APIView
from .services import (
    abort_video_upload,
    complete_video_upload,
    create_video_upload,
    sign_video_parts,
    video_part_count
)

from .models import Media_asset
from .serializers import ImageUploadRequestSerializer, MediaAssetSerializer,VideoCompleteSerializer,VideoPartSerializer,VideoUploadStartSerializer
from .services import complete_image_upload, create_image_upload
from apps.core.pagination import StandardResultsPagination

class ImageUploadRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        serializer = ImageUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        asset,presigned = create_image_upload(
            user= request.user,
            **serializer.validated_data,
        )

        return Response(
            {
                'asset' : MediaAssetSerializer(asset).data,
                'upload' : presigned,
            },
            status=status.HTTP_201_CREATED,
        )

class ImageUploadCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        asset = get_object_or_404(
            Media_asset,
            pk=id,
            uploaded_by=request.user,
            media_type=Media_asset.MediaType.IMAGE,
        )

        asset = complete_image_upload(asset)

        return Response(MediaAssetSerializer(asset).data)


def visible_media(user):
    queryset = Media_asset.objects.select_related('uploaded_by')

    if getattr(user,'role',None) == 'admin':
        return queryset
    return queryset.filter(uploaded_by=user)


class MediaAssetsListView(generics.ListAPIView):
    serializer_class = MediaAssetSerializer
    pagination_class = StandardResultsPagination
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,filters.SearchFilter,filters.OrderingFilter]
    filterset_fields = ['media_type','status']
    search_fields = ['file_name','alt_text']
    ordering_fields = ['created_at','file_size']
    ordering = ['-created_at']

    def get_queryset(self):
        return visible_media(self.request.user)


class MediaAssetDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = MediaAssetSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    http_method_names = ['get','patch','head','options']

    def get_queryset(self):
        return visible_media(self.request.user)


def _get_own_video_upload(request,id):
    """An in-progress video upload belonging to this user (404 otherwise)."""
    asset = get_object_or_404(
        Media_asset,
        pk = id,
        media_type = Media_asset.MediaType.VIDEO,
        uploaded_by=request.user
    )

    if asset.status != Media_asset.Status.UPLOADING or not asset.multipart_upload_id:
        raise ValidationError({'detail':'This upload is no longer in progress.'})
    return asset

class VideoUploadStartView(APIView):
    """POST /api/v1/media/video-uploads/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = VideoUploadStartSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        asset = create_video_upload(
            request.user,
            data['video'],
            data['file_name'],
            data['file_size'],
            data['mime_type'],
        )

        return Response(
            {
                'asset': MediaAssetSerializer(asset, context={'request': request}).data,
                'part_size': settings.MEDIA_VIDEO_PART_SIZE,
                'part_count': video_part_count(asset.file_size),
            },
            status=status.HTTP_201_CREATED,
        )


class VideoUploadPartsView(APIView):
    """POST /api/v1/media/<id>/video/parts/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        asset = _get_own_video_upload(request, id)

        serializer = VideoPartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        urls = sign_video_parts(asset, serializer.validated_data['part_numbers'])
        return Response({'urls': urls})


class VideoUploadCompleteView(APIView):
    """POST /api/v1/media/<id>/video/complete/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        asset = _get_own_video_upload(request, id)

        serializer = VideoCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        asset = complete_video_upload(asset, serializer.validated_data['parts'])
        return Response(MediaAssetSerializer(asset, context={'request': request}).data)


class VideoUploadAbortView(APIView):
    """POST /api/v1/media/<id>/video/abort/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        asset = _get_own_video_upload(request, id)
        abort_video_upload(asset)
        return Response(status=status.HTTP_204_NO_CONTENT)