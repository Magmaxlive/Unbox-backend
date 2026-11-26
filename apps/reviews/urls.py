from django.urls import path
from .views import ReviewQueueView

urlpatterns = [
    path('',ReviewQueueView.as_view(),name='review-queue')
]