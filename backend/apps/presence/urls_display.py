"""Token-addressed screen protocol, mounted at /api/v1/ (outside the HMAC public prefix: the screen's secret)."""
from django.urls import path

from .views_display import DisplayRegisterView, DisplayStateHeaderView, DisplayStateView

urlpatterns = [
    path("space-displays/register/", DisplayRegisterView.as_view(), name="space-display-register"),
    path("space-displays/state/", DisplayStateHeaderView.as_view(), name="space-display-state-header"),
    # Deprecated (decision 335d): the secret in the path. Kept briefly for old pages; redacted from every log.
    path("space-displays/<str:token>/state/", DisplayStateView.as_view(), name="space-display-state"),
]
