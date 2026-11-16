"""Root-mounted framable event card; `/embed/` is already a reserved first segment."""

from django.urls import path

from .views_embed import EventEmbedView

urlpatterns = [
    path("embed/<slug:makerspace_slug>/<uuid:public_token>/", EventEmbedView.as_view(), name="public-event-embed"),
]
