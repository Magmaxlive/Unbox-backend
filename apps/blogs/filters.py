import django_filters
from .models import Blog

class Blogfilter(django_filters.FilterSet):
    created_after = django_filters.IsoDateTimeFilter(
        field_name='created_at',
        lookup_expr='gte'
    )

    created_before = django_filters.filters.IsoDateTimeFilter(
        field_name='created_at'
        lookup_expr='lt'
    )

    class Meta:
        model = Blog
        fields = ['status','category']