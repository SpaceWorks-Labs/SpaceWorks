"""Repair route side effects retain their optional channel / To-Buy policies (128 C-4/C-9)."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.integrations.models import EmailLog
from apps.maintenance.models import IssueAssignment, RepairPart, TechnicianDispatch
from apps.maintenance.repairs import services_issues as svc
from apps.payments.models_ledger_entries import LedgerEntry
from apps.procurement.models import ToBuyItem
from tests.maintenance.l16_helpers import external, world
from tests.maintenance.route_support_cx11b_g3 import audit_delta, send
from tests.modules.switch_matrix_object_helpers import client_for, response_pair
from tests.modules.test_switch_matrix_objects_rest_support import switch

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory,
              pytest.mark.area_machines, pytest.mark.area_bookings]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("channel", ["email", "sms", "whatsapp", "telegram"])
def test_dispatch_records_channel_off_failure_and_restored_send(channel, native, monkeypatch, settings):
    # A sending switch disables this send, not the repair job or its durable
    # dispatch log (128 C-4); admission switches are tested by the step shards.
    settings.NOTIFICATION_FANOUT_VIA_CELERY = False
    w = world("g3-dispatch-policy")
    row = svc.open_issue(w.manager, w.space, subject_type="inventory_product", subject=w.product, title="Broken handle")
    contact = external(w, channels=[channel], telegram_chat_id="424242", telegram_opted_in_at=timezone.now(),
                       sms_opted_in_at=timezone.now(), whatsapp_opted_in_at=timezone.now())
    if channel != "email":
        contact.email = ""
        contact.save(update_fields=["email"])
    client = client_for(w.manager, w.space, native)
    # Gate and consent code is real. Only sender configuration/provider I/O and
    # the asynchronous enqueue are isolated; no email policy/log is replaced.
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", Mock())
    monkeypatch.setattr("apps.integrations.telegram.send_message", lambda *a, **k: True)
    monkeypatch.setattr("apps.integrations.messaging.resolver.resolve_sender", lambda *a: SimpleNamespace())
    monkeypatch.setattr("apps.integrations.messaging.templates.binding_for", lambda *a:
                        SimpleNamespace(template_name="repair", language="en", parameters=["makerspace.name"]))
    provider = Mock(return_value=SimpleNamespace(message_id="g3-provider", error_code=""))
    monkeypatch.setattr("apps.integrations.messaging.transport.send_message", provider)
    debt_count = LedgerEntry.objects.count()
    stock = (w.product.total_quantity, w.product.available_quantity, w.product.issued_quantity)
    for index, disabled in enumerate((False, True, False), 1):
        original = switch(w.space, channel) if disabled else None
        calls = provider.call_count
        with audit_delta(w.space, {"issue.dispatched": 1, "dispatch.sent": 1}):
            response = send(client, "admin-issue-dispatch", [row.pk], "post",
                            {"contact_ids": [contact.pk], "channels": [channel], "note": "Repair request"})
        assert response_pair(response) == (200, None)
        dispatches = TechnicianDispatch.objects.filter(issue=row).order_by("pk")
        assert dispatches.count() == index
        saved = dispatches.last()
        assert (saved.contact_id, saved.channel, saved.status, saved.failure_code) == (
            contact.pk, channel, "failed" if disabled else "delivered",
            ("email_not_sent" if channel == "email" else channel + "_off") if disabled else "")
        assert IssueAssignment.objects.filter(issue=row, contact=contact).count() == 1
        if channel == "email":
            email = EmailLog.objects.get(pk=int(saved.provider_message_id.split(":")[1]))
            assert email.to_email == contact.email
            assert email.status == ("skipped" if disabled else "pending")
            if disabled:
                assert email.error == "Email is disabled for this makerspace."
        elif channel in {"sms", "whatsapp"}:
            assert provider.call_count == calls + (0 if disabled else 1)
        w.product.refresh_from_db()
        assert (w.product.total_quantity, w.product.available_quantity, w.product.issued_quantity) == stock
        assert LedgerEntry.objects.count() == debt_count
        if disabled:
            switch(w.space, channel, original=original)
    assert row.assignments.count() == 1


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("area", ["inventory", "machines"])
def test_needed_part_keeps_need_but_creates_to_buy_only_while_policy_is_on(area, native):
    w = world("g3-parts-policy")
    subject, kind = (w.product, "inventory_product") if area == "inventory" else (w.machine, "machine")
    row = svc.open_issue(w.manager, w.space, subject_type=kind, subject=subject, title="Broken handle")
    client = client_for(w.manager, w.space, native)
    key = "inventory.tobuy" if area == "inventory" else "machines.tobuy"
    before_stock = w.product.available_quantity
    for index, disabled in enumerate((False, True, False), 1):
        original = switch(w.space, key) if disabled else None
        with audit_delta(w.space, {"repair.parts_needed": 1, "procurement.item_added": 0 if disabled else 1}):
            response = send(client, "admin-issue-parts", [row.pk], "post",
                            {"kind": "needed", "name": "New handle", "quantity": 2})
        assert response_pair(response) == (200, None)
        parts = RepairPart.objects.filter(issue=row).order_by("pk")
        assert parts.count() == index
        saved = parts.last()
        assert (saved.kind, saved.name, saved.quantity) == ("needed", "New handle", 2)
        if disabled:
            assert saved.to_buy_item_id is None
        else:
            item = ToBuyItem.objects.get(pk=saved.to_buy_item_id)
            assert (item.kind, item.name, item.quantity) == ("hardware" if area == "inventory" else "printing", "New handle", 2)
        w.product.refresh_from_db()
        assert w.product.available_quantity == before_stock
        if disabled:
            switch(w.space, key, original=original)
    assert ToBuyItem.objects.filter(makerspace=w.space).count() == 2
