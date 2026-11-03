from django.shortcuts import render
from .models import Blog
from rest_framework import generics
from .serializers import BlogSerializer
from accounts.permissions import IsAdminOrReadOnly,IsAdminRole,IsContributorRole
from rest_framework.permissions import IsAuthenticated


# Create your views here.
class Blog_list_create_View(generics.ListCreateAPIView):
    serializer_class = BlogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.role == 'admin':
            return Blog.objects.select_related('contributor','category','cover_image')

        return Blog.objects.select_related('contributor','category','cover_image').filter(contributor=user)
        
    def perform_create(self, serializer):
        return serializer.save(contributor=self.request.user)   
