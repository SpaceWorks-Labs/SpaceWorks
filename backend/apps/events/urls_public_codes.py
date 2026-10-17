"""Integrator attaches under api/v1 after token-target scope registration."""

from django.urls import path
from .views_public_codes import PublicEventCodeView

urlpatterns = [path("public/event-codes/<uuid:public_token>/", PublicEventCodeView.as_view(), name="public-event-code")]
