"""Per-space security settings, platform locks and superadmin PII windows."""

from django.urls import path

from apps.accounts.views_pii_access import PiiAccessView

from .views_security_settings import SecuritySettingLockView, SecuritySettingsView

BASE = "makerspaces/<int:makerspace_id>/"
urlpatterns = [
    path(BASE + "security-settings", SecuritySettingsView.as_view(), name="admin-makerspace-security-settings"),
    path(BASE + "security-settings/<str:key>/lock", SecuritySettingLockView.as_view(),
         name="admin-makerspace-security-lock"),
    path(BASE + "pii-access", PiiAccessView.as_view(), name="admin-makerspace-pii-access"),
]
