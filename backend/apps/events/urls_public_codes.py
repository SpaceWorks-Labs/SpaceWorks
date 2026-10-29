"""Integrator attaches under api/v1 after token-target scope registration."""

from django.urls import path, re_path
from .views_public_codes import PublicEventCodeView, PublicEventShortCodeView

urlpatterns = [
    # The 7-character base62 short code first; a UUID has hyphens and never matches it.
    re_path(r"^public/event-codes/(?P<code>[0-9A-Za-z]{7})/$", PublicEventShortCodeView.as_view(),
            name="public-event-short-code"),
    path("public/event-codes/<uuid:public_token>/", PublicEventCodeView.as_view(), name="public-event-code"),
]
