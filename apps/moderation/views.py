from django.shortcuts import render,get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from .services import perform_transition
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.permissions import IsAuthenticated

from apps.core.pagination import StandardResultsPagination
from .models import ContentActivity
from .rules import get_view_denial
from .serializers import ContentActivitySerializer
from .services import perform_transition
from apps.accounts.permissions import IsAdminRole
from .bulk import bulk_change_category,bulk_transition,bulk_delete
from .serializers import BulkActionSerializer,BulkCategorySerializer

# Create your views here.
class EditorialTransitionView(APIView):
    permission_classes = [IsAuthenticated]
    model = None
    serializer_class = None
    transition = None

    def get_queryset(self):
        return self.model.objects.visible_to(self.request.user)

    def post(self,request,id):
        content = get_object_or_404(self.get_queryset(),pk=id)
        updated = perform_transition(content,request.user,self.transition,reason=request.data.get('reason',''),)
        serializer = self.serializer_class(updated,context={'request':request})
        return Response(serializer.data)

class EditorialActivityListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ContentActivitySerializer
    pagination_class = StandardResultsPagination
    model = None

    def get_queryset(self):
        user = self.request.user
        content = get_object_or_404(
            self.model.objects.visible_to(user),
            pk = self.kwargs['id']
        )

        denial = get_view_denial(user,content)
        if denial:
            raise PermissionDenied(denial)
        
        return ContentActivity.for_content(content)


class EditorialBulkTransitionView(APIView):
    permission_classes = [IsAuthenticated,IsAdminRole]
    model = None
    transition = None
    ALLOWED_TRANSITIONS = ('archive','restore')

    def post(self,request):
        if self.transition not in self.ALLOWED_TRANSITIONS:
            raise ValidationError({'detail':'This bulk action is not available.'})

        serializer = BulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = bulk_transition(
            self.model,
            request.user,
            serializer.validated_data['ids'],
            self.transition,
        )

        return Response(result)


class EditorialBulkCategoryView(APIView):
    permission_classes = [IsAuthenticated]
    model = None

    def post(self,request):
        serializer = BulkCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = bulk_change_category(
            self.model,
            request.user,
            serializer.validated_data['ids'],
            serializer.validated_data['category']
        )

        return Response(result)


class EditorialBulkDeleteView(APIView):
    """
    POST /<content>/bulk/delete/   {"ids": [...]}
    Admin-only, permanent. Subclasses set `model`.
    """

    permission_classes = [IsAuthenticated]
    model = None

    def post(self, request):
        serializer = BulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = bulk_delete(
            self.model,
            request.user,
            serializer.validated_data['ids'],
        )
        return Response(result)