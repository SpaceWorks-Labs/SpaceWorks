"""Recomputing canonical charges cannot double-count an outstanding upload debt."""
from io import StringIO

import pytest
from django.core.management import call_command

from apps.evidence import storage
from apps.makerspaces.limits_usage import _storage
from tests.evidence.test_storage_reservations_cx7_p5 import world, upload

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_evidence_uploads]


def test_recompute_keeps_unconverted_evidence_in_the_reservation_only(settings, monkeypatch):
    space, actor, _ = world(settings, monkeypatch)
    photo = upload(space, actor)
    reads = []
    def head(key):
        reads.append(key)
        return 10
    monkeypatch.setattr(storage, "object_size", head)
    call_command("recompute_storage", str(space.pk), stdout=StringIO())
    space.refresh_from_db()
    assert space.storage_bytes_used == 0
    assert _storage(space) == 10
    assert photo.object_key not in reads
