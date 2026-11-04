"""Apple's pass web service under /api/v1/wallet/apple/ (release 2 L3; pass-token auth, no account)."""
from django.urls import path

from .wallet.views_apple import ApplePassLatestView, ApplePassLogView, ApplePassRegistrationView, ApplePassSerialsView

urlpatterns = [
    path("apple/v1/devices/<str:device>/registrations/<str:pass_type>/<str:serial>", ApplePassRegistrationView.as_view(),
         name="wallet-apple-registration"),
    path("apple/v1/devices/<str:device>/registrations/<str:pass_type>", ApplePassSerialsView.as_view(),
         name="wallet-apple-serials"),
    path("apple/v1/passes/<str:pass_type>/<str:serial>", ApplePassLatestView.as_view(), name="wallet-apple-pass"),
    path("apple/v1/log", ApplePassLogView.as_view(), name="wallet-apple-log"),
]
