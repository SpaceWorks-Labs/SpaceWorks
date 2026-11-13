"""Per-space security settings, platform locks and superadmin PII windows."""

from django.urls import path

from apps.accounts.views_pii_access import PiiAccessView
from apps.encryption.key_events import MakerspaceKeyEventsView

from .views_security_settings import SecuritySettingLockView, SecuritySettingsView

BASE = "makerspaces/<int:makerspace_id>/"
urlpatterns = [
    path(BASE + "security-settings", SecuritySettingsView.as_view(), name="admin-makerspace-security-settings"),
    path(BASE + "security-settings/<str:key>/lock", SecuritySettingLockView.as_view(),
         name="admin-makerspace-security-lock"),
    path(BASE + "pii-access", PiiAccessView.as_view(), name="admin-makerspace-pii-access"),
    # Lane L8 (#120): read-only rotation / re-key history; rotating is a /control/ action.
    path(BASE + "security/key-events", MakerspaceKeyEventsView.as_view(), name="admin-makerspace-key-events"),
]
