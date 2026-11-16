"""EP-43 / OR-3: room alert text and self-creation policy reasons go through gettext/ngettext."""
from types import SimpleNamespace
from unittest import mock

from django.test import override_settings

from apps.events.mentoring.chat_alerts import alert_text
from apps.organizations.services_self_service import creation_policy

PAYLOAD = {"category": "hardware", "team_alias": "Team 4", "priority": "high"}
EVENT = SimpleNamespace(pk=3, title="Hack Night", makerspace=object())


def _text(count):
    with mock.patch("apps.integrations.notification_links.local_link", return_value="https://x/y"):
        return alert_text(EVENT, PAYLOAD, count)


def test_alert_text_plural_forms_in_the_default_language():
    assert "1 mentor is on shift" in _text(1)
    assert "3 mentors are on shift" in _text(3)
    assert _text(2).startswith("Mentor help needed at Hack Night: hardware for Team 4 (priority high).")


@override_settings(ORGANIZATION_SELF_CREATION_ENABLED=False)
def test_policy_reason_is_translated_text_when_disabled():
    actor = SimpleNamespace(email="a@example.test", email_verified_at=None, is_tenant_dump_stub=False,
                            must_change_password=False)
    with mock.patch("apps.organizations.services_self_service.governance.member_account", return_value=True), \
            mock.patch("apps.accounts.native_session.is_native_session", return_value=False):
        assert creation_policy(actor)["reason"] == "Organization self-creation is disabled by the operator."
