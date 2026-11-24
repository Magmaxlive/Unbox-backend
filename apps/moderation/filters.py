import django_filters


class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    """Comma-separated values, e.g. ?status_in=draft,rejected"""


class EditorialContentFilter(django_filters.FilterSet):
    """
    Filters shared by editorial content lists (blogs, videos).
    Subclasses add their own Meta (model + exact-match fields).
    """

    
    created_after = django_filters.IsoDateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.IsoDateTimeFilter(field_name='created_at', lookup_expr='lt')

    # Readable alternative to ?category=<uuid>, used by dashboard URLs.
    category_slug = django_filters.CharFilter(field_name='category__slug')

    # Several statuses at once (bulk-action modes list only eligible items).
    status_in = CharInFilter(field_name='status', lookup_expr='in')