from django.urls import path

from .views_integration import (
    IntegrationEventDetailView, IntegrationEventListView, IntegrationEventParticipantsView,
)

urlpatterns = [
    path("", IntegrationEventListView.as_view(), name="integration-event-list"),
    path("<int:pk>/", IntegrationEventDetailView.as_view(), name="integration-event-detail"),
    path("<int:pk>/participants/", IntegrationEventParticipantsView.as_view(),
         name="integration-event-participants"),
]
