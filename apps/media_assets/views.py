from django.shortcuts import get_object_or_404
from rest_framework import status,filters,generics
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Media_asset
from .serializers import ImageUploadRequestSerializer, MediaAssetSerializer
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