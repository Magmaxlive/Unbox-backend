
from .models import Blog
from apps.moderation.filters import EditorialContentFilter

class Blogfilter(EditorialContentFilter):
    class Meta:
        model = Blog
        fields = ['status','category']