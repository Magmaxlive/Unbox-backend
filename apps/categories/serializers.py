from rest_framework import serializers
from .models import *

class Category_serializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id','name','slug','created_by','created_at','description','updated_at','is_active']
        read_only_fields = ['id','slug','created_by','created_at','updated_at']