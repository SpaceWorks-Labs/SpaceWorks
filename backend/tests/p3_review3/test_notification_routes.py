from types import SimpleNamespace as Bag

import pytest
from django.utils import timezone

from apps.apiclients.notifications_p2 import content as api_content
from apps.bookings.notifications import requester_content, staff_content
from apps.events.notification_envelopes import _owner_link, _staff_link
from apps.integrations.notification_builtin import send_builtin
from apps.integrations.notification_links import external_links, local_link
from apps.makerspaces import notifications_p2_broadcasts as broadcasts
from apps.makerspaces.notifications_p2_members import member_body, request_body
from apps.makerspaces.notifications_p2_subdomains import content as domain_content
from apps.makerspaces.notifications_p2_terms import term_body
from apps.makerspaces.notifications_p2_vouches import content as vouch_content
from apps.notifications.models_inbox import NotificationInboxRow
from apps.operations.notifications_p2 import staff_link
from apps.operations.notifications_p2_alerts import stocktake_body
from apps.payments.notifications_p2 import document_body, rendered as payment_body

pytestmark = pytest.mark.django_db


@pytest.fixture(params=["central", "pending_domain", "verified_domain"])
def routes(lane, request, settings, monkeypatch):
    settings.PUBLIC_APP_BASE_URL = "https://central.example"
    # Self-host trusts a custom domain at once, so a genuinely PENDING domain only exists on managed hosting.
    if request.param == "pending_domain":
        settings.PLATFORM_DOMAIN_SUFFIX = "spaceworks.example"
    home = lane.space
    home.frontend_domain = "custom.example" if request.param != "central" else ""
    home.frontend_domain_status = "verified" if request.param == "verified_domain" else "pending"
    home.save(update_fields=["frontend_domain", "frontend_domain_status"])
    prefix = "" if request.param == "verified_domain" else f"/m/{home.slug}"
    external = "https://custom.example" if request.param == "verified_domain" else f"https://central.example{prefix}"
    message = lambda *args, **kwargs: {"subject": "Update", "text_body": "Body", "html_body": ""}
    monkeypatch.setattr("apps.integrations.email_templates.render", message)
    monkeypatch.setattr("apps.bookings.notifications.render", message)
    return Bag(home=home, prefix=prefix, external=external, owner=lane.owner)


def _rendered(body):
    """Fan-out hands staff bodies over lazily (rendered in the recipient locale); call them."""
    return body() if callable(body) else body


def assert_links(routes, bodies):
    for index, (name, body, tail) in enumerate(bodies):
        assert body["link"] == f"{routes.prefix}/{tail}", name
        envelope = Bag(makerspace=routes.home, makerspace_id=routes.home.pk, audience="staff", scope={},
                       recipient_id=routes.owner.pk, feature="events",
                       event="updated", dedup_key=f"review3:routes:{index}")
        result = send_builtin(Bag(channel="in_app", envelope=envelope), body)
        assert result.accepted, name
        row = NotificationInboxRow.objects.get(pk=int(result.provider_id.split(":")[1]))
        assert row.link == body["link"], name
        assert external_links(routes.home, body)["link"] == f"{routes.external}/{tail}", name


def test_every_staff_destination_and_owner_content_has_a_local_route(routes, monkeypatch):
    home = routes.home
    row = Bag(pk=17, makerspace=home, space=Bag(makerspace=home), space_id=8, status="pending",
        state="revoked", decision_reason="", request_id=9, requested_label="custom", note="",
        label="Integration", resolution_note="", amount="10", currency="USD", due_at=None)
    term = Bag(membership=Bag(makerspace=home), membership_id=1, status="active")
    document = Bag(kind="receipt", makerspace=home, get_kind_display=lambda: "Receipt", number="R1", currency="USD", amount="10")
    monkeypatch.setattr(broadcasts, "load", lambda _: Bag(makerspace=home, title="News", body="Community news"))
    bodies = [(tab, {"link": staff_link(home, tab)}, f"admin/{tab}") for tab in (
        "payments", "stocktake", "devices", "reports", "members", "api-access", "settings", "email-log")]
    bodies += [
        ("event staff", {"link": _staff_link(home, row)}, "admin/events?event=17"),
        ("booking staff", staff_content(row, "created", {}), "admin/bookings?view=requests&status=pending"),
        ("stocktake staff", stocktake_body(row, "scheduled"), "admin/stocktake"),
        ("API staff", api_content(row, "staff"), "admin/api-access"),
        ("domain staff", domain_content(row, "staff"), "admin/settings"),
        ("domain owner", domain_content(row, "requester"), "admin/settings"),
        ("membership staff", member_body(row, "verified", "staff"), "admin/members"),
        ("application staff", request_body(row, "invitation", "staff"), "admin/members"),
        ("booking owner", requester_content(row, "created", {}), "member/bookings"),
        ("event owner ticket", {"link": _owner_link(home, Bag(pk=17, status="registered"))}, "member/events/17/ticket"),
        ("event pending owner", {"link": _owner_link(home, row)}, "member"),
        ("API owner", api_content(row, "requester"), "member"),
        ("membership owner", member_body(row, "verified", "requester"), "member"),
        ("application owner", request_body(row, "declined", "requester"), "member"),
        ("invited owner", request_body(row, "invitation", "requester"), "member/account-portal?section=invitations"),
        ("term owner", term_body(term, "renewal_due"), "member"),
        ("vouch owner", vouch_content(row, "requester"), "member"),
        ("broadcast owner", broadcasts.render(None), "member"),
        ("payment owner", payment_body(row, "charge_raised", "requester"), "member"),
        ("payment staff", payment_body(row, "charge_raised", "staff"), "admin/payments"),
        ("document owner", document_body(document), "member"),
    ]
    assert_links(routes, bodies)


def test_old_prefixed_links_keep_external_canonicalization_and_never_rebind_another_tenant(routes):
    home = routes.home
    old = {"link": f"/m/{home.slug}/member/events/4/ticket"}
    assert external_links(home, old)["link"] == f"{routes.external}/member/events/4/ticket"
    assert old["link"].startswith(f"/m/{home.slug}/")
    foreign = {"link": "/m/another/admin/reports"}
    assert external_links(home, foreign) == foreign
    assert local_link(home, "admin", "events?event=4") == f"{routes.prefix}/admin/events?event=4"


def test_inventory_and_membership_broadcast_emit_local_owner_links(routes, monkeypatch):
    from apps.inventory import notifications_p2 as inventory
    calls = []
    monkeypatch.setattr(inventory, "fanout", lambda **kwargs: calls.append(kwargs))
    watch = Bag(pk=1, makerspace=routes.home, product_id=73, user=routes.owner,
                created_at=timezone.now(), ready_at=timezone.now())
    inventory.notify_watch(watch, Bag(title="Available", body="A tool is back"))
    monkeypatch.setattr(broadcasts, "fanout", lambda **kwargs: calls.append(kwargs))
    campaign = Bag(pk=1, makerspace=routes.home, created_at=timezone.now(), title="News", body="Body")
    broadcasts.notify_broadcast(campaign, user_id=routes.owner.pk, segment={})
    assert len(calls) == 2
    assert_links(routes, [("stock watch", calls[0]["own"], "items/73"),
                          ("member campaign", calls[1]["owner_body"], "member")])


def test_device_report_and_failed_email_staff_notices(routes, monkeypatch):
    from unittest.mock import Mock
    from apps.devices import notifications_p2 as devices
    from apps.operations import notifications_p2_alerts as alerts, notifications_p2_reports as reports
    calls = []
    edge = Bag(pk=1, device_name="Door", created_at=timezone.now())
    rows = Mock()
    rows.filter.return_value.order_by.return_value.first.return_value = edge
    monkeypatch.setattr(devices, "scoped", lambda *_: rows)
    monkeypatch.setattr(devices, "fanout", lambda **kwargs: calls.append(kwargs))
    device = Bag(pk=3, kind="scanner", last_seen_at=timezone.now(), offline_since=timezone.now())
    devices.notify_device_state(routes.home, device, "offline", now=timezone.now())
    monkeypatch.setattr(alerts, "fanout", lambda **kwargs: calls.append(kwargs))
    alerts.notify_email_failure(Bag(pk=9, makerspace=routes.home, makerspace_id=routes.home.pk,
                                    event="updated", attempts=1, status="failed"))
    report = reports.content(Bag(schedule=Bag(makerspace=routes.home, report_key=next(iter(reports.REPORT_REGISTRY)))))
    assert len(calls) == 2
    assert_links(routes, [("device", _rendered(calls[0]["staff_body"]), "admin/devices"),
                          ("failed mail", _rendered(calls[1]["staff_body"]), "admin/email-log"),
                          ("report", report, "admin/reports")])


def test_shared_research_owner_inbox_link(routes, monkeypatch):
    from apps.integrations import notifications_research as research
    from apps.integrations.email_templates_registry_helpers import bag
    monkeypatch.setattr(research, "render", lambda *_: {"subject": "Update", "text_body": "Body", "html_body": ""})
    monkeypatch.setattr(research, "notify_lifecycle", lambda _space, **kwargs: kwargs["build"]())
    payload = research.notify_family(routes.home, "payments", "charge_raised", bag(id=1, status="pending"),
        data={}, member_id=routes.owner.pk, include_staff=False)
    assert len(payload.inbox) == 1
    assert_links(routes, [("shared research owner", {"link": payload.inbox[0].link}, "member")])
