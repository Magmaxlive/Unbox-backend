from django.shortcuts import render,get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .services import perform_transition

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
