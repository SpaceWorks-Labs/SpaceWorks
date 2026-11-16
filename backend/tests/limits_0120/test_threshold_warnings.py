"""Decision 328a: the 80 / 100 percent warnings notify once per crossing and reset when usage drops."""
import pytest
from django.core.cache import cache

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.boxes.models import Box
from apps.managed_hosting.limit_overview import overview_rows
from apps.managed_hosting.limit_thresholds import sweep_all, sweep_space
from apps.managed_hosting.models import PlatformLimitDefault, SpaceLimitThreshold
from apps.notifications.models_inbox import NotificationInboxRow
from tests.makerspaces.l4_helpers import space_with_manager
from tests.open_items_0120.test_platform_credential_limits import _limit

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _off(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False
    cache.clear()
    yield
    cache.clear()


def _boxes(space, count):
    # Labels are unique per makerspace (uniq_box_label_per_makerspace) and tests delete
    # b0..bN rows, so the next label is the first unused one, not the current row count.
    used = set(Box.objects.filter(makerspace=space).values_list("label", flat=True))
    have, n = len(used), 0
    while have < count:
        if f"b{n}" not in used:
            Box.objects.create(makerspace=space, label=f"b{n}")
            have += 1
        n += 1


def _root(name="th-root"):
    return User.objects.create_user(username=name, password="Root password 77!", account_kind="platform",
                                    role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)


def test_a_space_with_no_limits_is_skipped_and_nothing_is_written():
    space, _manager = space_with_manager("th-none")
    _boxes(space, 5)
    assert sweep_space(space) == {"notified": [], "reset": []}
    assert not SpaceLimitThreshold.objects.exists() and not NotificationInboxRow.objects.exists()


def test_below_eighty_percent_is_quiet():
    space, _manager = space_with_manager("th-quiet")
    _limit(space, boxes=10)
    _boxes(space, 7)
    assert sweep_space(space)["notified"] == []


def test_eighty_percent_warns_managers_and_superadmin_once():
    space, manager = space_with_manager("th-warn")
    root = _root()
    _limit(space, boxes=10)
    _boxes(space, 8)
    assert sweep_space(space)["notified"] == [("boxes", 80)]
    rows = NotificationInboxRow.objects.filter(makerspace=space, event="platform_limit.warning")
    assert set(rows.values_list("user_id", flat=True)) == {manager.pk, root.pk}
    assert "80%" in rows.get(user=manager).summary and "Contact the platform operator" in rows.get(user=manager).summary
    assert SpaceLimitThreshold.objects.get(makerspace=space, key="boxes").level == 80
    assert AuditLog.objects.filter(action="managed_hosting.limit_threshold_crossed", makerspace=space).count() == 1
    assert sweep_space(space)["notified"] == []  # the second sweep does not repeat
    assert rows.count() == 2


def test_hundred_percent_sends_the_reached_notice_and_keeps_existing_data():
    space, manager = space_with_manager("th-full")
    _limit(space, boxes=10)
    _boxes(space, 8)
    sweep_space(space)
    _boxes(space, 10)
    assert sweep_space(space)["notified"] == [("boxes", 100)]
    row = NotificationInboxRow.objects.get(makerspace=space, user=manager, event="platform_limit.reached")
    assert "reached its limit" in row.summary and "existing data is untouched" in row.summary
    assert Box.objects.filter(makerspace=space).count() == 10


def test_dropping_below_eighty_resets_so_the_next_crossing_notifies_again():
    space, _manager = space_with_manager("th-reset")
    _limit(space, boxes=10)
    _boxes(space, 8)
    sweep_space(space)
    Box.objects.filter(makerspace=space, label__in=["b0", "b1", "b2"]).delete()
    result = sweep_space(space)
    assert result["reset"] == ["boxes"] and not SpaceLimitThreshold.objects.exists()
    _boxes(space, 9)
    assert sweep_space(space)["notified"] == [("boxes", 80)]


def test_falling_from_full_to_the_warning_band_keeps_the_eighty_marker():
    space, _manager = space_with_manager("th-band")
    _limit(space, boxes=10)
    _boxes(space, 10)
    assert sweep_space(space)["notified"] == [("boxes", 100)]
    Box.objects.filter(makerspace=space, label="b0").delete()
    assert sweep_space(space)["notified"] == []
    assert SpaceLimitThreshold.objects.get(makerspace=space).level == 80
    _boxes(space, 10)
    assert sweep_space(space)["notified"] == [("boxes", 100)]


def test_removing_the_limit_clears_the_marker():
    space, _manager = space_with_manager("th-clear")
    _limit(space, boxes=10)
    _boxes(space, 9)
    sweep_space(space)
    _limit(space, boxes=-1)
    assert sweep_space(space)["reset"] == ["boxes"]


def test_a_platform_default_alone_drives_the_warning_for_every_space():
    one, _m1 = space_with_manager("th-def-a")
    two, _m2 = space_with_manager("th-def-b")
    PlatformLimitDefault.objects.create(key="boxes", value=5)
    cache.clear()
    _boxes(one, 4)
    _boxes(two, 1)
    totals = sweep_all()
    assert totals["notified"] == 1
    assert SpaceLimitThreshold.objects.get().makerspace_id == one.pk


def test_notification_stays_in_its_own_space():
    space, manager = space_with_manager("th-iso-a")
    other, other_manager = space_with_manager("th-iso-b")
    _limit(space, boxes=10)
    _boxes(space, 9)
    sweep_space(space)
    assert not NotificationInboxRow.objects.filter(makerspace=other).exists()
    assert other_manager.pk not in NotificationInboxRow.objects.values_list("user_id", flat=True)
    assert manager.pk in NotificationInboxRow.objects.values_list("user_id", flat=True)


def test_overview_rows_carry_module_group_source_and_level():
    space, _manager = space_with_manager("th-rows")
    _limit(space, boxes=10)
    _boxes(space, 9)
    [row] = overview_rows(space, limited_only=True)
    assert (row["key"], row["module"], row["group"], row["source"], row["level"]) == ("boxes", "qr_management", "inventory", "override", "warning")
    assert row["used"] == 9 and row["percent"] == 90.0


def test_the_sweep_is_scheduled():
    from config.settings import CELERY_BEAT_SCHEDULE
    assert CELERY_BEAT_SCHEDULE["limit-threshold-sweep"]["task"] == "apps.managed_hosting.tasks.sweep_limit_thresholds_task"
    from apps.operations.cloud_jobs.catalog import LEGACY_ENTRIES
    assert any(row[0] == "limit-threshold-sweep" for row in LEGACY_ENTRIES)
