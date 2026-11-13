"""Fresh-process runtime registration, independent of retained models/objects."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("tombstone,active", [("events", "bookings"), ("bookings", "events")])
def test_website_domains_boot_independently_and_keep_retention(tombstone, active):
    code = f"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from apps.makerspaces.website_visibility import _adapters
from apps.backup.object_ownership_registry import FIELD_OBJECT_RULES
from apps.data_export.classification import EXPORTED_MODEL_FIELDS
assert {active!r} in _adapters
assert {tombstone!r} not in _adapters
assert 'bookings.BookingResourcePageAsset' in EXPORTED_MODEL_FIELDS
assert any(rule.model_label == 'bookings.BookingResourcePageAsset' for rule in FIELD_OBJECT_RULES)
"""
    backend = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-c", code], cwd=backend, capture_output=True,
                            text=True, timeout=60, env={**os.environ, "TOMBSTONED_APPS": tombstone})
    assert result.returncode == 0, result.stdout + result.stderr
