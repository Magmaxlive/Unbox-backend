from django.shortcuts import render
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ImageUploadRequestSerializer,MediaAssetSerializer
from .services import create_image_upload

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
