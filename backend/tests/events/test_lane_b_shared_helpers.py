"""Shared primitives expose bounds and compensation without domain authorization."""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from django.db import transaction
from PIL import Image
from rest_framework.exceptions import ValidationError

from apps.inventory import public_image_storage
from apps.makerspaces.confirmation_render import google_calendar_url, render_confirmation_png
from apps.makerspaces.resource_clone import AssetCopies, OwnedImage, bounded_children, clone_transaction, copy_fields
from apps.operations.cancellation_restore import (
    RestoreRefused, record_cancellation, require_exact_restore, require_restorable, restore_deadline,
)
from tests.events.lane_b_helpers import fake_storage
from tests.events.ticketing_helpers import event_space


def test_copy_fields_is_an_explicit_deep_copy_and_children_are_bounded():
    source = SimpleNamespace(title="Resource", form=[{"id": "q"}], secret="credential")
    copied = copy_fields(source, ("title", "form"))
    copied["form"][0]["id"] = "changed"
    assert copied.keys() == {"title", "form"} and source.form == [{"id": "q"}]
    assert bounded_children([1, 2], maximum=2) == [1, 2]
    with pytest.raises(ValidationError):
        bounded_children([1, 2, 3], maximum=2)


def image(space, source_key, *, maximum=1000):
    return OwnedImage(source_key=source_key, source_prefix=f"event/{space.pk}/",
                      destination_prefix=f"event/{space.pk}/", max_bytes=maximum)


@pytest.mark.django_db(transaction=True)
def test_clone_context_commits_new_key_and_quota_and_compensates_storage_on_rollback(monkeypatch):
    space = event_space("shared-clone")
    key, objects, _, deleted = fake_storage(monkeypatch, space)
    with clone_transaction() as assets:
        created = assets.copy_image(space, image(space, key), storage=public_image_storage)
    space.refresh_from_db()
    assert created != key and objects[created] == 123 and space.storage_bytes_used == 123
    with pytest.raises(RuntimeError):
        with clone_transaction() as assets:
            failed = assets.copy_image(space, image(space, key), storage=public_image_storage)
            raise RuntimeError("domain transaction failed")
    space.refresh_from_db()
    assert space.storage_bytes_used == 123 and failed not in objects
    assert key in objects and created in objects and deleted.call_count == 1


@pytest.mark.django_db(transaction=True)
def test_timed_out_copy_is_enlisted_for_cleanup_before_io(monkeypatch):
    space = event_space("shared-timeout")
    key, objects, copied, deleted = fake_storage(monkeypatch, space)

    def fail_after_write(source, target):
        objects[target] = objects[source]
        raise RuntimeError("uncertain storage timeout")

    copied.side_effect = fail_after_write
    with pytest.raises(RuntimeError):
        with clone_transaction() as assets:
            assets.copy_image(space, image(space, key), storage=public_image_storage)
    assert objects == {key: 123} and deleted.call_count == 1
    space.refresh_from_db(); assert space.storage_bytes_used == 0


@pytest.mark.django_db(transaction=True)
def test_nested_clone_transaction_refuses_an_unobservable_outer_rollback():
    with transaction.atomic():
        with pytest.raises(RuntimeError, match="durable"):
            with clone_transaction():
                pytest.fail("Nested clone transaction must not open")


@pytest.mark.django_db
@pytest.mark.parametrize("case", ["foreign", "missing", "too_large", "total_bytes"])
def test_storage_copy_bounds_refuse_before_writing_an_asset(case, monkeypatch):
    space = event_space("shared-bounds")
    key, objects, copied, _ = fake_storage(monkeypatch, space)
    declaration = image(space, key)
    if case == "foreign":
        declaration = image(space, f"event/{space.pk + 10}/foreign.png")
    elif case == "missing":
        objects.clear()
    elif case == "too_large":
        declaration = image(space, key, maximum=100)
    copies = AssetCopies(max_total_bytes=100 if case == "total_bytes" else 1000)
    with pytest.raises(ValidationError):
        copies.copy_image(space, declaration, storage=public_image_storage)
    assert copied.call_count == 0
    space.refresh_from_db(); assert space.storage_bytes_used == 0


def provenance():
    now = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
    row = SimpleNamespace(status="registered", cancelled_at=None, status_before_cancel="")
    assert record_cancellation(row, now=now) == ("cancelled_at", "status_before_cancel")
    row.status = "cancelled"
    return row, now


def test_restore_window_has_exact_boundary_and_preserves_previous_state():
    row, now = provenance()
    assert restore_deadline(row) == now + timedelta(minutes=5)
    kwargs = {"cancelled_status": "cancelled", "allowed_statuses": ("registered",)}
    assert require_restorable(row, now=now, **kwargs) == "registered"
    assert require_restorable(row, now=now + timedelta(minutes=5, microseconds=-1), **kwargs) == "registered"
    for instant in (now - timedelta(microseconds=1), now + timedelta(minutes=5)):
        with pytest.raises(RestoreRefused) as failure:
            require_restorable(row, now=instant, **kwargs)
        assert str(failure.value.detail["code"]) == "window_expired"


@pytest.mark.parametrize("flag,reason", [("has_charge", "historical_charge"), ("has_consumption", "consumed_code"), ("would_charge", "charge_required")])
def test_restore_never_recreates_money_or_consumed_credentials(flag, reason):
    row, now = provenance()
    with pytest.raises(RestoreRefused) as failure:
        require_restorable(row, now=now, cancelled_status="cancelled", allowed_statuses=("registered",), **{flag: True})
    assert str(failure.value.detail["code"]) == reason
    assert row.status == "cancelled"


def test_exact_restore_refuses_a_downgrade():
    assert require_exact_restore("registered", "registered") is None
    with pytest.raises(RestoreRefused) as failure:
        require_exact_restore("registered", "waitlisted")
    assert str(failure.value.detail["code"]) == "admission_changed"


@pytest.mark.parametrize("title", ["Workshop", "सत्र 工作坊 مرحبا"])
def test_confirmation_render_is_a_valid_bounded_png_for_unicode_titles(title):
    rendered = render_confirmation_png(qr_value="a86ce324-cd84-4ec3-93b2-29ccdeab8633", title=title,
                                       lines=("Maker", "20 Oct 2026", "Main hall", "registered"))
    with Image.open(BytesIO(rendered)) as image:
        assert image.format == "PNG" and image.mode == "RGB"
        assert 640 <= image.width <= 2048 and image.height <= 2048
        image.verify()


def test_render_limits_and_timezone_aware_calendar_format():
    with pytest.raises(ValueError):
        render_confirmation_png(qr_value="x" * 513, title="Too long")
    with pytest.raises(ValueError):
        render_confirmation_png(qr_value="token", title="Title", lines=tuple(str(n) for n in range(9)))
    start = datetime(2026, 10, 20, 10, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    query = parse_qs(urlparse(google_calendar_url(title="Public & event", starts_at=start,
        ends_at=start + timedelta(hours=2), description="Public introduction", location="Hall")).query)
    assert query["dates"] == ["20261020T043000Z/20261020T063000Z"]
    assert set(query) == {"action", "text", "dates", "details", "location"}
    with pytest.raises(ValueError, match="timezone-aware"):
        google_calendar_url(title="Title", starts_at=start.replace(tzinfo=None), ends_at=start)
