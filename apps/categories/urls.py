from django.urls import path
from .views import *

urlpatterns = [
    path('',Category_list_create_view.as_view(),name='categories'),
    path('<uuid:id>/',Category_detailView.as_view(),name='categories'),
]