import pytest
from types import SimpleNamespace

from apps.integrations.dispatch_policy import EMAIL_MODULE_EXEMPT, email_module_blocks
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations import email
from tests.module_helpers import disable_module

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("function,args", [
    ("send_password_reset_email", ("owner@example.test", "https://example.test/reset#opaque")),
    ("send_email_verification_otp", ("owner@example.test", "123456")),
])
def test_security_mail_remains_synchronous_redacted_platform_email(lane, monkeypatch, function, args):
    # Exercise the existing mail helpers, never the envelope adapters.
    calls = []
    def dispatch(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status="sent", Status=SimpleNamespace(SENT="sent"))
    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email", dispatch)
    getattr(email, function)(*args)
    assert calls[0]["makerspace"] is None
    assert calls[0]["persist_body"] is False
    assert calls[0]["sync"] is True
    assert not NotificationEnvelope.objects.exists()


def test_module_exemptions_and_platform_gate_are_unchanged(lane):
    assert EMAIL_MODULE_EXEMPT == {
        ("account", "password_reset"), ("account", "email_verification"),
        ("hardware", "return_reminder"),
        # S-B: security alerts and the unusual-sign-in code (#62).
        ("account", "security_login_new_device"), ("account", "security_password_changed"),
        ("account", "security_mfa_changed"), ("account", "security_account_locked"),
        ("account", "security_login_code"),
    }
    disable_module(lane.space, "email")
    for stream, event in EMAIL_MODULE_EXEMPT:
        assert not email_module_blocks(lane.space, stream, event)
    assert not email_module_blocks(None, "governance", "makerspace_archive_requested")
    assert email_module_blocks(lane.space, "membership", "approved")
