from types import SimpleNamespace as Bag

import pytest
from django.utils.html import escape

from apps.integrations.notification_links import external_links, local_link
from apps.makerspaces.website_directory import public_url

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("custom", [False, True])
@pytest.mark.parametrize("family,kind,tail", [
    ("events", "member", "events/2/ticket"), ("bookings", "member", "bookings"),
    ("hardware_requests", "member", ""), ("machines", "member", ""),
    ("inventory", "items", "7"), ("makerspaces", "member", ""),
    ("payments", "member", ""), ("apiclients", "admin", "api-access"),
    ("operations", "admin", "reports?a=1&b=2"), ("devices", "admin", "devices"),
    ("research", "member", ""),
])
def test_shared_outbound_content_keeps_navigation_in_both_alternatives(world, settings, custom, family, kind, tail):
    settings.PUBLIC_APP_BASE_URL = "https://central.example.test"
    space = world.space
    if custom:
        space.frontend_domain, space.frontend_domain_status = "custom.example.test", "verified"
    original = {"subject": family, "text": "Decision: declined; USD 12.50", "html": "<p>Decision: declined; USD 12.50</p>",
                "link": local_link(space, kind, tail)}
    result = external_links(space, original)
    url = public_url(space, kind, tail).rstrip("/")
    assert url in result["text"] and escape(url) in result["html"]
    assert result["text"].startswith(original["text"]) and result["html"].startswith(original["html"])
    assert original["link"].startswith("/") and not original["link"].startswith("//")
    assert external_links(space, result) == result


def test_payment_document_body_contains_canonical_url_and_local_inbox_link(world, settings):
    from apps.payments.notifications_p2 import document_body
    settings.PUBLIC_APP_BASE_URL = "https://central.example.test"
    document = Bag(kind="receipt", makerspace=world.space, get_kind_display=lambda: "Receipt", number="R<1>", currency="usd", amount="12.50")
    content = document_body(document)
    url = public_url(world.space, "member", "").rstrip("/")
    assert url in content["text"] and url in content["html"]
    assert "USD 12.50" in content["text"] and "USD 12.50" in content["html"]
    assert "R&lt;1&gt;" in content["html"] and "R<1>" not in content["html"]
    assert content["link"] == local_link(world.space, "member")


def test_smtp_source_rerender_preserves_outbound_links(world, monkeypatch):
    from apps.integrations.models_contract import NotificationDelivery
    from apps.integrations.notification_email_source import prepare
    from apps.integrations.delivery_content import content
    from apps.integrations.notification_resolution import DeliveryTarget
    envelope = world.envelope()
    delivery = NotificationDelivery.objects.create(envelope=envelope, makerspace=world.space,
        channel="email", target_key="email", provider="builtin")
    monkeypatch.setattr("apps.integrations.notification_resolution.eligible", lambda _: True)
    monkeypatch.setattr("apps.integrations.notification_resolution.resolve", lambda *_, **__: [DeliveryTarget("email")])
    monkeypatch.setattr("apps.integrations.notification_sources.render", lambda _: {
        "subject": "Notice", "text": "Body", "html": "<p>Body</p>", "link": local_link(world.space, "member")})
    monkeypatch.setattr("apps.hardware_requests.notifications_p2_email.render_email", lambda _, value: value)
    log = Bag(source_metadata={"delivery_id": delivery.pk}, source_id=envelope.pk,
              makerspace_id=world.space.pk, recipient_id=world.owner.pk)
    assert prepare(log)
    result = content(log)
    url = public_url(world.space, "member", "").rstrip("/")
    assert url in result.text_body and url in result.html_body


def test_digest_keeps_each_constituents_navigation(world, monkeypatch):
    from apps.integrations import notification_digest as digest
    constituent = Bag(makerspace=world.space, event="confirmed")
    monkeypatch.setattr(digest, "constituents", lambda _: [constituent])
    monkeypatch.setattr("apps.integrations.notification_sources.render", lambda _: {
        "subject": "Booking", "text": "Confirmed", "link": local_link(world.space, "member", "bookings")})
    assert public_url(world.space, "member", "bookings") in digest.render_digest(None)["text"]


def test_maintenance_meter_reason_is_escaped_in_html(world, monkeypatch):
    from apps.machines import notifications_p2_maintenance as notices
    machine = Bag(pk=4, makerspace=world.space, machine_type=Bag(pk=2))
    row = Bag(pk=8, machine=machine, machine_id=4, created_at="now", performed_by_id=world.staff.pk)
    captured = []
    monkeypatch.setattr(notices, "maintenance_context", lambda *_, **__: {})
    monkeypatch.setattr(notices, "render", lambda *_, **__: {"subject": "Due", "text_body": "Inspect", "html_body": "<p>Inspect</p>"})
    monkeypatch.setattr(notices, "fanout", lambda **kwargs: captured.append(kwargs))
    notices.notify(row, "overdue", due_reason="Usage > 100 & < 200")
    assert len(captured) == 1
    rendered = captured[0]["staff"]
    assert "Usage > 100 & < 200" in rendered["text"]
    assert "Usage &gt; 100 &amp; &lt; 200" in rendered["html"]
