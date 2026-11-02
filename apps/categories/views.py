from django.shortcuts import render
from apps.accounts.permissions import IsAdminOrReadOnly,IsAdminRole,IsContributorRole
from rest_framework import generics
from .serializers import *

class Category_list_create_view(generics.ListCreateAPIView):
    serializer_class = Category_serializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = Category.objects.select_related('created_by').all()

        if self.request.user.role != 'admin':
            queryset = Category.objects.filter(is_active = True)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)