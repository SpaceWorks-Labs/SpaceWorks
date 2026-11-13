"""Unusual-login check routes (lane S-B), mounted under ``/api/v1/auth/`` by ``urls_security``."""

from django.urls import path

from apps.accounts.views_devices import KnownDeviceDetailView, KnownDeviceListView
from apps.accounts.views_login_codes import LoginCodeResendView
from apps.accounts.views_security_alerts import SecurityAlertNotMeView

urlpatterns = [
    path("login-code/resend", LoginCodeResendView.as_view(), name="auth-login-code-resend"),
    path("devices", KnownDeviceListView.as_view(), name="auth-devices"),
    path("devices/<int:device_id>", KnownDeviceDetailView.as_view(), name="auth-device-detail"),
    path("security-alerts/not-me", SecurityAlertNotMeView.as_view(), name="auth-security-alerts-not-me"),
]
