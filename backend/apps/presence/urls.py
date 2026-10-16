from django.urls import path

from apps.presence.views import (
    PresenceCurrentView, PresenceEndView, PresenceStartView, PresenceRenewView,
    PresenceProjectsView, PresencePreferenceView,
)
from .views_public import PresenceNowView


urlpatterns = [
    path("makerspaces/<slug:makerspace_slug>/presence/now/", PresenceNowView.as_view(), name="public-presence-now"),
    path("<slug:makerspace_slug>/presence-sessions", PresenceStartView.as_view(), name="presence-start"),
    path("<slug:makerspace_slug>/presence-sessions/current", PresenceCurrentView.as_view(), name="presence-current"),
    path("<slug:makerspace_slug>/presence-sessions/current/end", PresenceEndView.as_view(), name="presence-end"),
    path("<slug:makerspace_slug>/presence-sessions/current/renew", PresenceRenewView.as_view(), name="presence-renew"),
    path("<slug:makerspace_slug>/presence-sessions/projects", PresenceProjectsView.as_view(), name="presence-projects"),
    path("<slug:makerspace_slug>/presence-sessions/preferences", PresencePreferenceView.as_view(), name="presence-preferences"),
]
