from django.urls import path

from .views import VideoDetailView,VideoListCreateView,VideoTransitionView,VideoActivityView

urlpatterns = [
    path('',VideoListCreateView.as_view(),name='video-list'),
    path('<uuid:id>/',VideoDetailView.as_view(),name='video-detail'),

    # editorial workflow
    path('<uuid:id>/submit/', VideoTransitionView.as_view(transition='submit'), name='video-submit'),
    path('<uuid:id>/withdraw/', VideoTransitionView.as_view(transition='withdraw'), name='video-withdraw'),
    path('<uuid:id>/publish/', VideoTransitionView.as_view(transition='publish'), name='video-publish'),
    path('<uuid:id>/reject/', VideoTransitionView.as_view(transition='reject'), name='video-reject'),
    path('<uuid:id>/archive/', VideoTransitionView.as_view(transition='archive'), name='video-archive'),
    path('<uuid:id>/restore/', VideoTransitionView.as_view(transition='restore'), name='video-restore'),

    # history
    path('<uuid:id>/activity/', VideoActivityView.as_view(), name='video-activity'),
]