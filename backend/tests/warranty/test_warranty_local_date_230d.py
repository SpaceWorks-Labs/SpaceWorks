"""Decision 230(d): a warranty's status is judged on the SPACE's own day, not the server's UTC day."""
from datetime import date, datetime, timezone
from types import SimpleNamespace

from apps.warranty import serializers as warranty_serializers


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 1, 1, 20, 0, tzinfo=timezone.utc)  # already 2 January in Kolkata


def test_status_uses_the_space_local_day_and_looks_it_up_once_per_space(monkeypatch):
    import apps.makerspaces.local_time as local_time
    seen, lookups = [], []
    monkeypatch.setattr(local_time, "datetime", _FrozenDatetime)
    monkeypatch.setattr(warranty_serializers, "warranty_status", lambda warranty, today: seen.append(today) or "active")

    class _Space(SimpleNamespace):
        @property
        def timezone(self):
            lookups.append(self.pk)
            return "Asia/Kolkata"

    space = _Space(pk=1)
    serializer = warranty_serializers.WarrantySerializer(context={})
    for _ in range(3):
        serializer.get_status(SimpleNamespace(makerspace_id=1, makerspace=space))
    assert seen == [date(2026, 1, 2)] * 3
    assert lookups == [1]


def test_a_utc_space_keeps_the_utc_day(monkeypatch):
    import apps.makerspaces.local_time as local_time
    seen = []
    monkeypatch.setattr(local_time, "datetime", _FrozenDatetime)
    monkeypatch.setattr(warranty_serializers, "warranty_status", lambda warranty, today: seen.append(today) or "active")
    obj = SimpleNamespace(makerspace_id=2, makerspace=SimpleNamespace(timezone="UTC"))
    warranty_serializers.WarrantySerializer(context={}).get_status(obj)
    assert seen == [date(2026, 1, 1)]
