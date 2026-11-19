
from django.contrib import admin
from django.urls import path,include
from drf_spectacular.views import (SpectacularAPIView,SpectacularSwaggerView)

urlpatterns = [
    # auth
    path('admin/', admin.site.urls),
    path('api/v1/auth/',include('apps.accounts.urls')),

    # category
    path('api/v1/category/',include('apps.categories.urls')),

    # blogs
    path('api/v1/blogs/',include('apps.blogs.urls')),

    # media
    path('api/v1/media/',include('apps.media_assets.urls')),

    # video
    path('api/v1/video/',include('apps.video.urls')),

    # drf spectacular
    path('api/schema/',SpectacularAPIView.as_view(),name='schema'),
    path('api/docs/',SpectacularSwaggerView.as_view(url_name='schema'),name='swagger-ui')
]
