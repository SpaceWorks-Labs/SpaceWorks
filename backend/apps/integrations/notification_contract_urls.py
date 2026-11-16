from django.urls import path

from .notification_api_channels import ChannelListView, ChannelSettingsView
from .notification_api_delivery import ContractDeliveryListView, ContractTestView
from .notification_api_personal import (
    EndpointListView, EndpointRevokeView, EndpointStartView, EndpointVerifyView, PersonalSelectionView,
)

urlpatterns = [
    path("makerspace/<int:makerspace_id>/channels", ChannelListView.as_view(), name="contract-channels"),
    path("makerspace/<int:makerspace_id>/channels/<str:channel>", ChannelSettingsView.as_view(), name="contract-channel"),
    path("makerspace/<int:makerspace_id>/personal/endpoints", EndpointListView.as_view(), name="contract-endpoints"),
    path("makerspace/<int:makerspace_id>/personal/endpoints/start", EndpointStartView.as_view(), name="contract-endpoint-start"),
    path("makerspace/<int:makerspace_id>/personal/challenges/<int:challenge_id>/verify", EndpointVerifyView.as_view(), name="contract-endpoint-verify"),
    path("makerspace/<int:makerspace_id>/personal/endpoints/<int:pk>", EndpointRevokeView.as_view(), name="contract-endpoint-revoke"),
    path("makerspace/<int:makerspace_id>/personal/preferences", PersonalSelectionView.as_view(), name="contract-preferences"),
    path("makerspace/<int:makerspace_id>/personal/deliveries", ContractDeliveryListView.as_view(), name="contract-deliveries"),
    path("makerspace/<int:makerspace_id>/channels-test", ContractTestView.as_view(), name="contract-test"),
]
