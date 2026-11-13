"""E-B8: a space's own SMTP is used only after a test message from it was accepted; sender name and reply-to."""
import pytest
from django.core.mail import EmailMessage

from apps.audit.models import AuditLog
from apps.integrations import email as email_module
from apps.integrations.space_sender import apply
from apps.integrations.space_smtp_gate import own_smtp_active, smtp_verified
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


def _smtp_space(slug):
    space = make_space(slug)
    space.smtp_host, space.smtp_port, space.smtp_from_email = "smtp.example.org", 587, "hello@example.org"
    space.set_smtp_password("pw")
    space.save()
    return space


def test_unverified_own_smtp_falls_back_to_the_platform_connection(monkeypatch):
    space = _smtp_space("eb8-unverified")
    sentinel = (object(), "platform@example.org")
    monkeypatch.setattr(email_module, "platform_mail_connection", lambda: sentinel)
    assert email_module.makerspace_mail_connection(space) == sentinel
    assert own_smtp_active(space) is False


def test_failed_probe_keeps_smtp_inactive_and_success_activates_until_edited(monkeypatch):
    from apps.integrations.mail_providers import probe_space
    space = _smtp_space("eb8-probe")
    client = authenticated_client(make_member("eb8-probe-sm", space))
    url = f"/api/v1/admin/makerspace/{space.pk}/email/test"

    def refuse(self, fail_silently=False):
        raise OSError("connection refused")

    monkeypatch.setattr(probe_space.EmailMultiAlternatives, "send", refuse)
    failed = client.post(url)
    assert failed.status_code == 422 and failed.json()["code"] == "smtp_probe_failed"
    space.refresh_from_db()
    assert smtp_verified(space) is False

    monkeypatch.setattr(probe_space.EmailMultiAlternatives, "send", lambda self, fail_silently=False: 1)
    ok = client.post(url)
    assert ok.status_code == 200 and ok.json()["smtp_verified"] is True
    space.refresh_from_db()
    assert own_smtp_active(space) is True
    meta = AuditLog.objects.filter(action="email.smtp_probe_ran").order_by("pk").last().meta
    assert meta == {"accepted": True, "code": "provider_accepted"}

    space.smtp_host = "smtp2.example.org"  # any edit to the account needs a fresh test
    space.save()
    assert smtp_verified(space) is False


def test_probe_needs_manage_makerspace_and_a_configured_account():
    space = make_space("eb8-noacct")
    client = authenticated_client(make_member("eb8-noacct-sm", space))
    assert client.post(f"/api/v1/admin/makerspace/{space.pk}/email/test").json()["code"] == "smtp_not_configured"
    other = make_space("eb8-other")
    assert client.post(f"/api/v1/admin/makerspace/{other.pk}/email/test").status_code in (403, 404)


def test_sender_name_and_reply_to_apply_without_changing_the_from_address():
    space = make_space("eb8-sender")
    space.email_from_name, space.email_reply_to = "Makers\nBcc: x", "desk@example.org"
    space.save()
    message = EmailMessage(from_email="noreply@example.org", to=["a@e.com"])
    apply(type("Log", (), {"makerspace": space, "pk": 1})(), message)
    assert "noreply@example.org" in message.from_email and "\n" not in message.from_email
    assert message.reply_to == ["desk@example.org"]
