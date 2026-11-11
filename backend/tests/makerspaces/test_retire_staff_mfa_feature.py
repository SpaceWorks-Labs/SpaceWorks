"""S-A: makerspaces 0119 retires security.staff_mfa_required (staff MFA is a platform rule, #62)."""

import pytest
from django.apps import apps
from django.db import connection

from apps.audit.models import AuditLog
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.migration_support.retire_staff_mfa import RETIRED_KEY, retire
from apps.makerspaces.models import Makerspace
from apps.makerspaces.models_security import MakerspaceSecurityLock
from apps.makerspaces.security_settings_registry import BY_KEY, FEATURE_KEYS

pytestmark = pytest.mark.django_db


def test_the_key_is_no_capability_and_no_security_setting():
    assert RETIRED_KEY not in FEATURES and RETIRED_KEY not in BY_KEY and not FEATURE_KEYS
    assert {"security.passkeys_allowed", "security.staff_session_max_hours",
            "security.staff_idle_timeout_minutes"} <= set(BY_KEY)


def test_migration_strips_the_key_deletes_locks_and_audits():
    from apps.accounts.models import User
    root = User.objects.create_superuser("retire-root", password="x" * 20)
    on = Makerspace.objects.create(name="On", slug="retire-on")
    locked = Makerspace.objects.create(name="Locked", slug="retire-locked")
    off = Makerspace.objects.create(name="Off", slug="retire-off")
    Makerspace.objects.filter(pk=on.pk).update(enabled_features=[*on.enabled_features, RETIRED_KEY])
    MakerspaceSecurityLock.objects.create(makerspace=locked, key=RETIRED_KEY, floor=True, locked_by=root)
    with connection.schema_editor() as editor:
        retire(apps, editor)
    assert RETIRED_KEY not in Makerspace.objects.get(pk=on.pk).enabled_features
    assert not MakerspaceSecurityLock.objects.filter(key=RETIRED_KEY).exists()
    rows = {row.makerspace_id: row.meta for row in AuditLog.objects.filter(action="makerspace.capability_retired")}
    assert set(rows) == {on.pk, locked.pk} and off.pk not in rows
    assert rows[on.pk]["was_enabled"] is True and rows[locked.pk]["lock_removed"] is True
    with connection.schema_editor() as editor:
        retire(apps, editor)  # idempotent: nothing left to retire, no new rows
    assert AuditLog.objects.filter(action="makerspace.capability_retired").count() == 2
