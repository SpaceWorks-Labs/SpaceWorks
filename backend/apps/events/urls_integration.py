from django.urls import path

from .views_integration import (
    IntegrationEventDetailView, IntegrationEventListView, IntegrationEventParticipantsView,
)
from .views_integration_orders import IntegrationOrderDetailView, IntegrationOrderListView

urlpatterns = [
    path("", IntegrationEventListView.as_view(), name="integration-event-list"),
    path("<int:pk>/", IntegrationEventDetailView.as_view(), name="integration-event-detail"),
    path("<int:pk>/participants/", IntegrationEventParticipantsView.as_view(),
         name="integration-event-participants"),
    path("orders/", IntegrationOrderListView.as_view(), name="integration-order-list"),
    path("orders/<int:pk>/", IntegrationOrderDetailView.as_view(), name="integration-order-detail"),
]
