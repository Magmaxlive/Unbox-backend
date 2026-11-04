from django.shortcuts import render
from apps.accounts.permissions import IsAdminOrReadOnly,IsAdminRole,IsContributorRole
from rest_framework import generics,filters
from .serializers import *
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import ProtectedError
from apps.core.pagination import StandardResultsPagination


class Category_list_create_view(generics.ListCreateAPIView):
    serializer_class = Category_serializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend,filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name','description']

    def get_queryset(self):
        queryset = Category.objects.select_related('created_by')

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
        queryset = Category.objects.select_related('created_by')
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