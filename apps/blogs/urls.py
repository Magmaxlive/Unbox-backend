from django.urls import path
from .views import *

urlpatterns = [
    path('',Blog_list_create_View.as_view(),name='blogs'),
    path('<uuid:id>/',BlogDetailView.as_view(),name='blogs'),

    # editorial workflow
    path('<uuid:id>/submit/',BlogTransitionView.as_view(transition='submit'),name='blog-submit'),
    path('<uuid:id>/withdraw/',BlogTransitionView.as_view(transition='withdraw'),name='blog-withdraw'),
    path('<uuid:id>/publish/',BlogTransitionView.as_view(transition='publish'),name='blog-publish'),
    path('<uuid:id>/reject/',BlogTransitionView.as_view(transition='reject'),name='blog-reject'),
    path('<uuid:id>/archive/',BlogTransitionView.as_view(transition='archive'),name='blog-archive'),
    path('<uuid:id>/restore/',BlogTransitionView.as_view(transition='restore'),name='blog-restore'),

]