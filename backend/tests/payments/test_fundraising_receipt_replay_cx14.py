"""R5: restored tax receipts freeze once even across stale/concurrent reissues."""

from copy import deepcopy
from threading import Barrier, Event, Thread
from time import monotonic, sleep
from unittest.mock import Mock

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections

from apps.audit.models import AuditLog
from apps.integrations.notify import NotificationResult
from apps.payments.donations import notices, tax_receipts, views_staff_area
from apps.payments.donations.models import Donation
from tests.l18_local.helpers import admin, charge_for, gift, settle_offline, setup, staff, switch, tax_ready
from tests.modules.switch_matrix_object_helpers import _no_write, client_for
from tests.money_modes.helpers import OFFLINE, set_mode
from tests.payments.test_fundraising_mutations_cx14 import snapshot

pytestmark = [pytest.mark.area_payments, pytest.mark.django_db(transaction=True)]
TAX = "finance.tax_exempt_receipts"


def restored_tax_world(monkeypatch, settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.NOTIFICATION_FANOUT_VIA_CELERY = False
    sent = []

    def send(space, row, event, **kwargs):
        sent.append((row.pk, event, deepcopy(row.tax_receipt), kwargs["marker"], kwargs["text"]))
        return NotificationResult(True)

    monkeypatch.setattr(notices, "_send", send)
    monkeypatch.setattr("apps.payments.notifications.notify_payment", Mock())
    monkeypatch.setattr("apps.payments.notifications_p2.notify_document", Mock())
    space, manager, donor = setup("cx14-r5-receipt")
    set_mode(space, "donations", OFFLINE)
    switch(space, "billing.maker_checker", on=False)
    tax_ready(space)
    donation, _response = gift(space, donor, amount="25", wants_tax_receipt=True,
                              donor_pan="ABCDE1234F", donor_address="12 Maker Road")
    switch(space, TAX, on=False)
    settle_offline(manager, charge_for(donation))
    donation.refresh_from_db()
    assert (donation.status, donation.tax_receipt) == ("paid", None)
    assert donation.paid_at is not None
    switch(space, TAX)
    actor = staff("cx14-r5-receipt", space, "fundraising")
    sent.clear()
    return space, actor, donation, sent


def test_freeze_reloads_stale_gift_and_returns_identical_first_snapshot(monkeypatch, settings):
    space, _actor, gift_row, sent = restored_tax_world(monkeypatch, settings)
    first, stale = [Donation.objects.get(pk=gift_row.pk) for _ in range(2)]
    assert first.tax_receipt is None and stale.tax_receipt is None
    audits = list(AuditLog.objects.order_by("pk").values())
    frozen = deepcopy(tax_receipts.freeze(first))
    assert frozen is not None
    assert frozen["issued_at"]
    assert frozen["amount"] == "25.00"
    assert stale.tax_receipt is None  # Separate instance still predates the first freeze.
    with connection.execute_wrapper(_no_write):
        replay = tax_receipts.freeze(stale)
    assert replay == frozen
    assert stale.tax_receipt == first.tax_receipt == frozen
    assert Donation.objects.get(pk=gift_row.pk).tax_receipt == frozen
    assert replay["issued_at"] == frozen["issued_at"]
    assert list(AuditLog.objects.order_by("pk").values()) == audits
    assert sent == []
    # Frozen metadata is reusable with optional switches off, still immutable.
    switch(space, "finance.donations", TAX, on=False)
    assert tax_receipts.freeze(stale) == frozen
    stale.tax_receipt = {**frozen, "issued_at": "changed"}
    with pytest.raises(ValidationError) as refused:
        stale.save(update_fields=["tax_receipt"])
    assert refused.value.messages == ["A tax-exempt receipt is frozen once issued."]
    assert Donation.objects.get(pk=gift_row.pk).tax_receipt == frozen


def test_concurrent_endpoint_reissues_after_tax_restoration_reuse_first_snapshot(monkeypatch, settings):
    assert connection.vendor == "postgresql"
    space, actor, donation, sent = restored_tax_world(monkeypatch, settings)
    apis = [client_for(actor, space, False) for _ in range(2)]
    before = snapshot(space)
    audits = set(AuditLog.objects.values_list("pk", flat=True))
    looked_up, frozen, release = Barrier(2), Event(), Event()
    loaded, pids, receipts, results, errors, first_pids = [], [], [], [], [], []
    original_lookup, original_freeze = views_staff_area.gift_or_404, tax_receipts.freeze

    def lookup(*args, **kwargs):
        row = original_lookup(*args, **kwargs)  # Both real scoped lookups see NULL.
        loaded.append(row.tax_receipt)
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            pids.append(cursor.fetchone()[0])
        looked_up.wait(timeout=8)
        return row

    def freeze(row):
        result = original_freeze(row)
        receipts.append(deepcopy(result))
        if len(receipts) == 1:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                first_pids.append(cursor.fetchone()[0])
            frozen.set()  # Outer donation_write still holds makerspace and gift.
            assert release.wait(8), "First reissue was never released"
        return result

    monkeypatch.setattr(views_staff_area, "gift_or_404", lookup)
    monkeypatch.setattr(tax_receipts, "freeze", freeze)

    def reissue(api):
        close_old_connections()
        db = connections["default"]
        try:
            with db.cursor() as cursor:
                cursor.execute("SET lock_timeout = '8s'")
            response = api.post(admin(space, f"/{donation.pk}/receipt/reissue"))
            results.append((response.status_code, response.json()))
        except BaseException as exc:
            errors.append(exc)
        finally:
            db.close()

    threads = [Thread(target=reissue, args=(api,), daemon=True) for api in apis]
    for thread in threads:
        thread.start()
    try:
        assert frozen.wait(8), errors
        assert loaded == [None, None]
        other_pid = next(pid for pid in pids if pid != first_pids[0])
        blockers, deadline = [], monotonic() + 3
        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_blocking_pids(%s)", [other_pid])
                blockers = cursor.fetchone()[0]
            if first_pids[0] in blockers:
                break
            sleep(0.01)
        assert first_pids[0] in blockers, (errors, results)
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=12)
    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert sorted(status for status, _data in results) == [200, 200]
    assert len(receipts) == 2
    assert receipts == [receipts[0], receipts[0]]
    first_snapshot = receipts[0]
    assert first_snapshot["issued_at"]
    donation.refresh_from_db()
    assert donation.tax_receipt == first_snapshot
    assert [data["tax_receipt_number"] for _status, data in results] == [first_snapshot["number"]] * 2
    assert [data["status"] for _status, data in results] == ["paid", "paid"]
    assert len(sent) == 2
    assert [(pk, event, receipt) for pk, event, receipt, _marker, _text in sent] == [
        (donation.pk, "donation_received", first_snapshot)] * 2
    assert len({marker for _pk, _event, _receipt, marker, _text in sent}) == 2
    assert all(first_snapshot["number"] in text for _pk, _event, _receipt, _marker, text in sent)
    new_audits = list(AuditLog.objects.exclude(pk__in=audits).order_by("pk"))
    assert [row.action for row in new_audits] == ["donation.receipt_reissued"] * 2
    assert [row.actor_id for row in new_audits] == [actor.pk, actor.pk]
    assert [row.meta for row in new_audits] == [{"donation_id": donation.pk, "tax_receipt": True}] * 2
    after = snapshot(space)
    before[Donation._meta.label][0]["tax_receipt"] = first_snapshot
    assert after == before
