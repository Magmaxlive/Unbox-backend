import django_filters

class EditorialContentFilter(django_filters.filterset):
    """
    Filters shared by editorial content lists (blogs, videos).
    Subclasses add their own Meta (model + exact-match fields).
    """
    # date filter
    created_after = django_filters.IsoDateTimeFilter(field_name='created_at',lookup_expr='gte')
    created_before = django_filters.IsoDateTimeFilter(field_name='created_at',lookup_expr='lt')

    # category slug filter
    category_slug = django_filters.CharFilter(field_name='category__slug')