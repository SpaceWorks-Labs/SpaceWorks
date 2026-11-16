"""Exercise the real custom UserAdmin URL, including its wrapped callback."""

from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.admin.models import LogEntry, CHANGE
from django.test import Client, RequestFactory
from django.urls import resolve, reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.reauthentication_control import sensitive_control_request
from tests.accounts.mfa_helpers import force_mfa_login
from tests.accounts.test_reauthentication_control_links import PASSWORD, verify_control

pytestmark = pytest.mark.django_db
NEW_PASSWORD = "Replacement staff password 918!"


@pytest.mark.parametrize("proof", ["missing", "expired", "other_session", "recent"])
def test_custom_user_password_change_requires_recent_control_proof(client, proof):
    root = User.objects.create_superuser(username="password-control-root", password=PASSWORD)
    target = User.objects.create_user(username="password-control-member", password=PASSWORD)
    force_mfa_login(client, root)
    original_hash = target.password
    if proof == "other_session":
        other = Client()
        other.force_login(root)
        session = other.session
        session["mfa_version"] = client.session["mfa_version"]
        session.save()
        verify_control(other, root)
    elif proof != "missing":
        verify_control(client, root)
        if proof == "expired":
            ReauthenticationSession.objects.filter(user=root).update(
                auth_time=timezone.now() - timedelta(minutes=11))

    url = reverse("admin:auth_user_password_change", args=[target.pk])
    payload = {"password1": NEW_PASSWORD, "password2": NEW_PASSWORD, "set_usable_password": "true"}
    assert sensitive_control_request(RequestFactory().post(url, payload), resolve(url).func)
    assert client.get(url).status_code == 200
    response = client.post(url, payload)
    assert response.status_code == 302
    target.refresh_from_db()
    changes = LogEntry.objects.filter(user=root, object_id=str(target.pk), action_flag=CHANGE)
    if proof != "recent":
        destination = urlsplit(response.url)
        assert destination.path == "/mfa/reauth/"
        assert parse_qs(destination.query) == {"next": [url]}
        assert target.password == original_hash
        assert not changes.exists()
    else:
        assert response.url == reverse("admin:accounts_user_change", args=[target.pk])
        assert target.check_password(NEW_PASSWORD)
        assert changes.count() == 1
