from django.shortcuts import render
from apps.accounts.permissions import IsAdminOrReadOnly,IsAdminRole,IsContributorRole
from rest_framework import generics,filters
from .serializers import *
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import ProtectedError,Count
from apps.core.pagination import StandardResultsPagination
from rest_framework.views import APIView
from .services import move_category_content
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.response import Response



def annotate_usage(queryset):
    return queryset.annotate(
        blog_count = Count('blogs',distinct=True),
        video_count = Count('videos',distinct=True)
    )


class Category_list_create_view(generics.ListCreateAPIView):
    serializer_class = Category_serializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend,filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name','description']

    def get_queryset(self):
        queryset = annotate_usage(Category.objects.select_related('created_by')).order_by('-created_at')

        if self.request.user.role != 'admin':
            queryset = queryset.filter(is_active = True)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class Category_detailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = Category_serializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = 'id'

    def get_queryset(self):
        queryset = annotate_usage(Category.objects.select_related('created_by'))
        if self.request.user.role != 'admin':
            queryset = queryset.filter(is_active=True)
        return queryset

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise serializers.ValidationError(
                {'detail': 'Cannot delete this category because it is associated with existing videos or blogs'}
            )


class CategoryMoveContentView(APIView):
    permission_classes = [IsAuthenticated,IsAdminRole]

    def post(self,request,id):
        source = get_object_or_404(Category,pk=id)

        serializer = MoveContentSerializer(data=request.data,context={'source':source})
        serializer.is_valid(raise_exception=True)

        result = move_category_content(
            source,
            serializer.validated_data['target_category'],
            request.user,
            deactivate_source=serializer.validated_data['deactivate_source'],
        )

        return Response(result)