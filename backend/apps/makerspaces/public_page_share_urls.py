"""Integrator attaches at root after crawler and origin registrations land."""

from django.urls import path
from apps.separability.registry import runtime_active
from .public_page_share import PublicPageCoverShareView, PublicPageShareView

urlpatterns = [
    path("share/pages/<str:handle>/", PublicPageShareView.as_view(), name="public-page-share"),
    path("share/pages/<str:handle>/cover/", PublicPageCoverShareView.as_view(), name="public-page-cover-share"),
]
if runtime_active("events"):
    from apps.events.views_public_codes import PublicEventCodeShareView, PublicEventCoverShareView
    urlpatterns += [
        path("share/e/<uuid:public_token>/", PublicEventCodeShareView.as_view(), name="public-event-code-share"),
        path("share/e/<uuid:public_token>/cover/", PublicEventCoverShareView.as_view(), name="public-event-cover-share"),
        # Short codes are aliases of the same live gate (the view 404s any other shape);
        # the crawler card never counts a visit.
        path("share/e/<str:code>/", PublicEventCodeShareView.as_view(), name="public-event-short-code-share"),
        path("share/e/<str:code>/cover/", PublicEventCoverShareView.as_view(),
             name="public-event-short-code-cover-share"),
    ]
