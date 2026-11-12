from rest_framework import serializers
from .models import ContentActivity

class ContentActivitySerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source='get_action_display',read_only=True)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = ContentActivity
        fields = ['id','action','action_label','actor','actor_name','from_status','to_status','note','changed_fields','created_at']
        read_only_fields = fields

    def get_actor_name(self,obj):
        return obj.actor.name if obj.actor else None