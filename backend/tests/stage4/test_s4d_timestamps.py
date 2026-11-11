"""Staff inverse fixtures and raw digests retain PostgreSQL's full precision."""

from datetime import date, datetime, time, timezone
import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder

from apps.accounts.models import User
from apps.backup.raw_projection import concrete_record_payload, no_decrypt_guard, raw_records
from apps.backup.raw_projection import fixture_payload
from apps.backup.staff_shells import shell_fixture, staff_fixture
from apps.events.models import EventSeries
from apps.integrations.models import NotificationTimingPolicy
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.tenant_dump_raw import projected_raw_digest
from tests.account_split.p1_helpers import staff

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("microsecond", [0, 1, 123, 999, 1000, 123000, 123456, 999999])
@pytest.mark.parametrize("has_login", [False, True])
def test_staff_preimage_round_trip_preserves_every_concrete_column(microsecond, has_login):
    space = Makerspace.objects.create(name="Precise staff", slug="s4d-precise")
    account, _ = staff(space, "s4d-precise")
    stamp = datetime(2026, 10, 17, 12, 0, 0, microsecond, tzinfo=timezone.utc)
    User.objects.filter(pk=account.pk).update(date_joined=stamp, last_login=stamp if has_login else None)
    with no_decrypt_guard():
        record = raw_records(User.objects.filter(pk=account.pk), User)[0]
        fixture = staff_fixture(User, record)
    restored = {User._meta.pk.attname: fixture["pk"]}
    for name, value in fixture["fields"].items():
        field = User._meta.get_field(name)
        restored[field.attname] = field.to_python(value)
    assert restored == record
    assert concrete_record_payload(User, restored) == concrete_record_payload(User, record)
    # The deterministic shell must have the same JSON shape in both producers.
    shell = shell_fixture(fixture)
    shell_record = {User._meta.pk.attname: shell["pk"]}
    for name, value in shell["fields"].items():
        field = User._meta.get_field(name)
        shell_record[field.attname] = field.to_python(value)
    assert staff_fixture(User, shell_record) == shell


@pytest.mark.parametrize("microsecond", [0, 1, 123, 999, 1000, 123000, 123456, 999999])
def test_lane_d_digest_distinguishes_submillisecond_changes_and_survives_round_trip(microsecond):
    stamp = datetime(2026, 10, 17, 12, 0, 0, microsecond, tzinfo=timezone.utc)
    row = {"id": 1, "last_login": stamp}
    changed = {**row, "last_login": stamp.replace(microsecond=(microsecond + 1) % 1000000)}
    original = projected_raw_digest({"accounts.User": [row]})
    assert projected_raw_digest({"accounts.User": [changed]}) != original
    restored = {**row, "last_login": datetime.fromisoformat(stamp.isoformat())}
    assert projected_raw_digest({"accounts.User": [restored]}) == original
    if microsecond % 1000 == 0:
        # Millisecond-aligned rows retain the old canonical encoding.
        from apps.tenant_migration.tenant_dump_raw import _RawDigestEncoder
        assert json.dumps(row, cls=_RawDigestEncoder) == json.dumps(row, cls=DjangoJSONEncoder)


@pytest.mark.parametrize("microsecond", [0, 1, 123, 999, 1000, 123000, 123456, 999999])
@pytest.mark.parametrize("label", ["timing", "series"])
def test_time_columns_also_keep_precision_in_fixtures_and_lane_d_digests(microsecond, label):
    space = Makerspace.objects.create(name="Precise times", slug="s4d-time")
    clock = time(12, 30, 0, microsecond)
    if label == "timing":
        model = NotificationTimingPolicy
        instance, _ = model.objects.update_or_create(makerspace=space, defaults={
            "quiet_start": clock, "quiet_end": clock, "digest_at": clock,
        })
        fields = ["quiet_start", "quiet_end", "digest_at"]
    else:
        model = EventSeries
        instance = model.objects.create(makerspace=space, title="Precise series", recurrence_timezone="UTC",
            dtstart_local_date=date(2027, 1, 1), dtstart_local_time=clock,
            recurrence_rule="FREQ=DAILY;COUNT=2", duration_minutes=60)
        fields = ["dtstart_local_time"]
    row = raw_records(model.objects.filter(pk=instance.pk), model)[0]
    fixture = fixture_payload(model, [row])[0]
    restored = {model._meta.pk.attname: fixture["pk"]}
    for name, value in fixture["fields"].items():
        field = model._meta.get_field(name)
        restored[field.attname] = field.to_python(value)
    assert all(restored[field] == clock for field in fields)
    original = projected_raw_digest({model._meta.label: [row]})
    assert projected_raw_digest({model._meta.label: [restored]}) == original
    changed = {**row, fields[0]: clock.replace(microsecond=(microsecond + 1) % 1000000)}
    assert projected_raw_digest({model._meta.label: [changed]}) != original
