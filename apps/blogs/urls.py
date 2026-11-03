from django.urls import path
from .views import *

urlpatterns = [
    path('',Blog_list_create_View.as_view(),name='blogs'),
    # path('<uuid:id>/',Category_detailView.as_view(),name='categories'),
]