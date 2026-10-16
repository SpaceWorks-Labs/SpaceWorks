from django.urls import path

from .notification_wa_twilio_views import TwilioWhatsAppTemplateRefreshView, TwilioWhatsAppWebhookView

PREFIX = "makerspace/<int:makerspace_id>/whatsapp/twilio/"
urlpatterns = [
    path(PREFIX + "<int:generation>/inbound", TwilioWhatsAppWebhookView.as_view(),
         {"kind": "inbound"}, name="whatsapp-twilio-inbound"),
    path(PREFIX + "<int:generation>/status/<int:delivery_id>", TwilioWhatsAppWebhookView.as_view(),
         {"kind": "status"}, name="whatsapp-twilio-status"),
    path(PREFIX + "templates/refresh", TwilioWhatsAppTemplateRefreshView.as_view(),
         name="whatsapp-twilio-template-refresh"),
]
