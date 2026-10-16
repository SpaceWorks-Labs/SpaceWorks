"""Integrator mounts this sibling URL list; factory registration belongs in ready()."""
from django.urls import path

from .notification_wa_meta_views import MetaWebhookView

urlpatterns = [
    path("makerspace/<int:makerspace_id>/whatsapp/meta/<int:generation>/<str:phone_number_id>/webhook",
         MetaWebhookView.as_view(), name="whatsapp-meta-webhook"),
]
