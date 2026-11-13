from django.urls import path

from apps.integrations.views_messaging_webhooks import MetaMessagingWebhookView, TwilioMessagingWebhookView

urlpatterns = [
    path("twilio/platform/status", TwilioMessagingWebhookView.as_view(), {"kind": "status"}, name="messaging-twilio-platform-status"),
    path("twilio/platform/inbound", TwilioMessagingWebhookView.as_view(), {"kind": "inbound"}, name="messaging-twilio-platform-inbound"),
    path("twilio/m/<int:makerspace_id>/status", TwilioMessagingWebhookView.as_view(), {"kind": "status"}, name="messaging-twilio-status"),
    path("twilio/m/<int:makerspace_id>/inbound", TwilioMessagingWebhookView.as_view(), {"kind": "inbound"}, name="messaging-twilio-inbound"),
    path("whatsapp/platform", MetaMessagingWebhookView.as_view(), name="messaging-meta-platform"),
    path("whatsapp/m/<int:makerspace_id>", MetaMessagingWebhookView.as_view(), name="messaging-meta"),
]
