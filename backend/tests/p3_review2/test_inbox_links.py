from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.bookings.notifications import staff_content
from apps.events.notification_envelopes import _staff_link
from apps.integrations.notification_builtin import send_builtin
from apps.integrations.notification_links import external_links
from apps.inventory.notifications_p2 import notify_watch
from apps.notifications.models_inbox import NotificationInboxRow
from apps.operations.notifications_p2 import staff_link
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("status,domain,external", [
    ("pending", "custom.example", "https://central.example/m/local-notices"),
    ("verified", "custom.example", "https://custom.example"),
    ("pending", "", "https://central.example/m/local-notices"),
])
def test_every_converted_staff_notice_keeps_open_action_and_external_canonical_url(settings, monkeypatch, status, domain, external):
    settings.PUBLIC_APP_BASE_URL = "https://central.example/"
    home, user = make_space("local-notices"), make_user("inbox-owner")
    home.frontend_domain, home.frontend_domain_status = domain, status
    bodies = [{"link": staff_link(home, tab)} for tab in (
        "payments", "stocktake", "devices", "reports", "members", "api-access", "settings", "email-log",
    )]
    bodies.append({"link": _staff_link(home, SimpleNamespace(pk=42))})
    monkeypatch.setattr("apps.bookings.notifications.render", lambda *_: {"subject": "Update", "text_body": "Body"})
    booking = SimpleNamespace(space=SimpleNamespace(makerspace=home), space_id=8, pk=9, status="pending")
    bodies.append(staff_content(booking, "created", {}))
    captured = []
    monkeypatch.setattr("apps.inventory.notifications_p2.fanout", lambda **kwargs: captured.append(kwargs))
    watch = SimpleNamespace(pk=1, makerspace=home, product_id=73, user=user,
                           created_at=timezone.now(), ready_at=timezone.now())
    notify_watch(watch, SimpleNamespace(title="Available", body="A tool is back"))
    bodies.append(captured[0]["own"])
    for index, body in enumerate(bodies):
        local = body["link"]
        prefix = "" if status == "verified" and domain else "/m/local-notices"
        assert local.startswith(prefix + "/")
        envelope = SimpleNamespace(makerspace=home, makerspace_id=home.pk, recipient_id=user.pk, feature="events", event="updated",
                               audience="staff", scope={}, dedup_key=f"link:{index}")
        result = send_builtin(SimpleNamespace(channel="in_app", envelope=envelope), body)
        assert result.accepted
        inbox = NotificationInboxRow.objects.get(pk=int(result.provider_id.split(":")[1]))
        assert inbox.link == local
        assert external_links(home, body)["link"] == external + local.removeprefix(prefix)
        assert body["link"] == local  # external conversion must not mutate the saved inbox body


def test_external_url_conversion_does_not_rebind_another_tenants_path():
    home = make_space("own-tenant")
    rendered = {"link": "/m/other-tenant/admin/reports"}
    assert external_links(home, rendered) == rendered


def test_delivery_gives_chat_absolute_urls_and_inbox_local_paths(contract, settings):
    from apps.integrations.notification_delivery import ensure_deliveries, send
    from apps.notifications.models_preferences import NotificationPreference
    c = contract
    settings.PUBLIC_APP_BASE_URL = "https://central.example"
    c.space.enabled_features = sorted(set(c.space.enabled_features) | {"notifications.member_inbox"})
    c.space.save(update_fields=["enabled_features"])
    NotificationPreference.objects.create(makerspace=c.space, user=c.user, category="hardware_requests",
                                          channels=["telegram", "in_app"], email_fallback=False)
    local = staff_link(c.space, "reports")
    envelope = c.envelope(rendered={"subject": "Report", "text": "Ready", "link": local})
    ensure_deliveries(envelope)
    assert set(envelope.deliveries.values_list("channel", flat=True)) == {"telegram", "in_app"}
    for delivery in envelope.deliveries.all():
        send(delivery.pk)
        delivery.refresh_from_db()
        # The fake chat provider acknowledges ("accepted"); the built-in inbox completes at once ("sent").
        assert delivery.state in {"accepted", "sent"}
    assert c.fake.calls[0][1]["link"] == f"https://central.example{local}"
    assert NotificationInboxRow.objects.get(user=c.user, makerspace=c.space).link == local
