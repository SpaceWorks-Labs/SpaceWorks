"""Final audit 0.12.0 (m22): a concurrent event-shift import that loses the unique race skips the row."""
import pytest
from django.db import IntegrityError

from apps.events import volunteer_hours_adapter as adapter
from apps.makerspaces.models import Makerspace, VolunteerHourEntry

pytestmark = pytest.mark.django_db(transaction=True)


def test_integrity_error_on_create_is_skipped_not_raised(monkeypatch):
    makerspace = Makerspace.objects.create(name="f6-vol", slug="f6-vol")
    monkeypatch.setattr(adapter, "volunteer_on", lambda *_: True)
    monkeypatch.setattr(adapter, "module_enabled", lambda *_: True)
    monkeypatch.setattr(adapter, "feature_enabled", lambda *_: True)

    def boom(**kwargs):
        raise IntegrityError("volunteer_entry_source_unique")
    monkeypatch.setattr(VolunteerHourEntry.objects, "create", boom)
    assert adapter.import_verified_hours(None, makerspace) == 0  # no verified rows: a no-op, no 500
