"""Integrator attaches under api/v1 after token-target scope registration.

The UUID route comes first; any other single segment falls through to the short-code
route, whose view accepts exactly 7 base62 characters and answers 404 otherwise. Plain
`path()` converters (not `re_path`) keep the route under the scanned `api/v1/public/`
prefix that the API-client and claim-route registries enumerate.
"""

from django.urls import path
from .views_public_codes import PublicEventCodeView, PublicEventShortCodeView

urlpatterns = [
    path("public/event-codes/<uuid:public_token>/", PublicEventCodeView.as_view(), name="public-event-code"),
    path("public/event-codes/<str:code>/", PublicEventShortCodeView.as_view(), name="public-event-short-code"),
]
