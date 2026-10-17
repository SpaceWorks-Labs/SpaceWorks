"""Integrator attaches at root after crawler and origin registrations land."""

from django.urls import path
from apps.separability.registry import runtime_active
from .public_page_share import PublicPageShareView

urlpatterns = [path("share/pages/<str:handle>/", PublicPageShareView.as_view(), name="public-page-share")]
if runtime_active("events"):
    from apps.events.views_public_codes import PublicEventCodeShareView
    urlpatterns += [path("share/e/<uuid:public_token>/", PublicEventCodeShareView.as_view(), name="public-event-code-share")]
