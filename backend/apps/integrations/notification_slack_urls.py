from django.urls import path
from .notification_slack_views import ChatOAuthCallbackView, ChatInboundView, SlackInstallStartView

urlpatterns = [
    path("makerspace/<int:makerspace_id>/slack/install/start", SlackInstallStartView.as_view(), name="notification-slack-install"),
    path("makerspace/<int:makerspace_id>/slack/oauth/callback", ChatOAuthCallbackView.as_view(channel="slack"), name="notification-slack-oauth"),
    path("makerspace/<int:makerspace_id>/slack/inbound", ChatInboundView.as_view(channel="slack"), name="notification-slack-inbound"),
]
