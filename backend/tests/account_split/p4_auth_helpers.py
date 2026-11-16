"""Produce real credential-workflow audit rows for retention/backup assertions."""
from cryptography.fernet import Fernet
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.mfa_crypto import new_secret, totp
from apps.accounts.models import UserMFA
from apps.accounts.services_mfa import enable
from apps.accounts.views_login import LoginView
from apps.accounts.views_password import ChangePasswordView
from apps.audit.models import AuditLog


def staff_auth_history(user, space, settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    space.enabled_features = sorted(set(space.enabled_features or []) - {"security.staff_mfa_required"})
    # Security keys change only through the security service; write the fixture row directly.
    type(space).objects.filter(pk=space.pk).update(enabled_features=space.enabled_features)
    password = "Initial-staff-pass-9087!"
    user.set_password(password)
    user.save(update_fields=["password"])
    factory = APIRequestFactory()
    login = factory.post("/api/v1/auth/login", {"username": user.username, "password": password,
        "surface": "staff", "context": "staff", "makerspace": space.slug}, format="json")
    response = LoginView.as_view()(login)
    assert response.status_code == 200 and "access" in response.data
    change = factory.post("/api/v1/auth/change-password", {
        "current_password": password, "new_password": "Rotated-staff-pass-9087!",
    }, format="json")
    force_authenticate(change, user=user)
    assert ChangePasswordView.as_view()(change).status_code == 200
    user.refresh_from_db()
    factor, _created = UserMFA.objects.get_or_create(user=user)
    secret = new_secret()
    assert enable(user, factor, secret, totp(secret, int(timezone.now().timestamp() // 30)))
    events = list(AuditLog.objects.filter(actor=user, makerspace=None,
        action__in=["auth.login_succeeded", "user.password_changed", "auth.mfa_enabled"]).order_by("pk"))
    assert len(events) == 3
    return events
