from django.shortcuts import render
from .models import Blog
from rest_framework import generics,filters
from .serializers import BlogSerializer
from apps.accounts.permissions import IsAdminOrReadOnly,IsAdminRole,IsContributorRole,IsOwnerOrAdmin
from rest_framework.permissions import IsAuthenticated
from apps.core.pagination import StandardResultsPagination
from django_filters.rest_framework import DjangoFilterBackend
from .filters import Blogfilter
from apps.moderation.permissions import EditorialContentPermission
from apps.moderation.views import EditorialTransitionView


# Create your views here.
class Blog_list_create_View(generics.ListCreateAPIView):
    serializer_class = BlogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend,filters.SearchFilter,filters.OrderingFilter]
    filterset_class = Blogfilter
    search_fields = ['title','contributor__name']
    ordering_fields = ['created_at','published_at','updated_at']

    def get_queryset(self):
        user = self.request.user
        queryset = Blog.objects.visible_to(user).select_related('contributor','category','cover_image').order_by('-created_at')

        if user.role == 'admin':
            return queryset

        return queryset.filter(contributor=user)
        
    def perform_create(self, serializer):
        return serializer.save(contributor=self.request.user)   


class BlogDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BlogSerializer
    permission_classes = [IsAuthenticated,EditorialContentPermission]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        queryset = Blog.objects.visible_to(user).select_related(
            "contributor",
            "category",
            "cover_image",
        )

        if user.role == 'admin':
            return queryset
        return queryset.filter(contributor=user)


class BlogTransitionView(EditorialTransitionView):
    model = Blog
    serializer_class = BlogSerializer