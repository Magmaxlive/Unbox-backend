from apps.moderation.filters import EditorialContentFilter
from .models import Video

class VideoFilter(EditorialContentFilter):
    class Meta:
        model = Video
        fields = ['category','status','source_type']