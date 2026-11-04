"""Passkey routes, mounted under ``/api/v1/auth/`` by ``urls_security``."""

from django.urls import path

from apps.accounts.passkeys import views

PASSKEY_ROUTE_NAMES = (
    "auth-passkeys", "auth-passkey-detail", "auth-passkeys-register-options", "auth-passkeys-register-verify",
    "auth-passkeys-authenticate-options", "auth-passkeys-authenticate-verify", "auth-mfa-passkey-options",
    "auth-reauth-passkey-options", "auth-reauth-passkey",
)

urlpatterns = [
    path("passkeys", views.PasskeyListView.as_view(), name="auth-passkeys"),
    path("passkeys/<int:passkey_id>", views.PasskeyDetailView.as_view(), name="auth-passkey-detail"),
    path("passkeys/register/options", views.PasskeyRegisterOptionsView.as_view(), name="auth-passkeys-register-options"),
    path("passkeys/register/verify", views.PasskeyRegisterVerifyView.as_view(), name="auth-passkeys-register-verify"),
    path("passkeys/authenticate/options", views.PasskeyAuthenticateOptionsView.as_view(),
         name="auth-passkeys-authenticate-options"),
    path("passkeys/authenticate/verify", views.PasskeyAuthenticateVerifyView.as_view(),
         name="auth-passkeys-authenticate-verify"),
    path("mfa/passkey/options", views.PasskeyMfaOptionsView.as_view(), name="auth-mfa-passkey-options"),
    path("reauth/passkey/options", views.PasskeyReauthOptionsView.as_view(), name="auth-reauth-passkey-options"),
    path("reauth/passkey", views.PasskeyReauthVerifyView.as_view(), name="auth-reauth-passkey"),
]
