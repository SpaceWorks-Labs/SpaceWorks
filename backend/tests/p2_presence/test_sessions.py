from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.presence import services
from apps.presence.models import PresenceSession
from apps.presence.policy import PresenceError

pytestmark = pytest.mark.django_db


def start(lane, **kwargs):
    options = dict(latitude=0, longitude=0)
    options.update(kwargs)
    return services.start_session(lane.owner, lane.space, 60, **options)


@pytest.mark.parametrize("minutes", [60, 120, 180, 240])
def test_default_hour_presets(lane, minutes):
    row = services.start_session(lane.owner, lane.space, minutes, latitude=0, longitude=0)
    assert row.expires_at - row.started_at == timedelta(minutes=minutes)
    assert row.account_id == row.member_id == lane.owner.pk


def test_custom_validated_presets(lane):
    lane.space.presence_preset_minutes = [30, 90]
    lane.space.save(update_fields=["presence_preset_minutes"])
    with pytest.raises(PresenceError) as error:
        start(lane)
    assert error.value.detail["code"] == "invalid_preset"
    assert services.start_session(lane.owner, lane.space, 90, latitude=0, longitude=0)


@pytest.mark.parametrize("coordinates,code", [
    ({}, "location_required"), ({"latitude": 0}, "location_required"),
    ({"latitude": 1, "longitude": 1}, "outside_geofence"),
    ({"latitude": 0, "longitude": 0, "accuracy": 100}, "location_inaccurate"),
    ({"latitude": float("nan"), "longitude": 0}, "location_invalid"),
    ({"latitude": 91, "longitude": 0}, "location_invalid"),
])
def test_hard_geofence(lane, coordinates, code):
    with pytest.raises(PresenceError) as error:
        services.start_session(lane.owner, lane.space, 60, **coordinates)
    assert error.value.detail["code"] == code
    assert not PresenceSession.objects.exists()


def test_accuracy_cannot_expand_radius(lane):
    # 111m from centre, outside the 100m radius, even with a 50m accuracy reading.
    with pytest.raises(PresenceError):
        start(lane, longitude=0.001, accuracy=50)


def test_no_geofence_refuses_self_but_staff_can_check_in(lane):
    lane.space.geofence_enabled = False
    lane.space.save(update_fields=["geofence_enabled"])
    with pytest.raises(PresenceError) as error:
        start(lane)
    assert error.value.detail["code"] == "geofence_unconfigured"
    assert services.staff_check_in(lane.staff, lane.owner, lane.space, 60).status == "visiting"


def test_coordinates_are_discarded(lane):
    row = start(lane, accuracy=5)
    assert not {"latitude", "longitude", "accuracy"} & {f.name for f in row._meta.fields}
    assert "latitude" not in str(AuditLog.objects.filter(makerspace=lane.space).values_list("meta", flat=True))


def test_working_requires_own_project(lane):
    with pytest.raises(PresenceError):
        start(lane, status="working")
    other = lane.person("other")
    from apps.makerspaces.models_account_profile import AccountProfile, AccountProject
    profile = AccountProfile.objects.create(user=other)
    foreign = AccountProject.objects.create(profile=profile, title="Private", public_visible=False)
    with pytest.raises(PresenceError):
        start(lane, status="working", project_id=foreign.pk)
    lane.project.public_visible = False
    lane.project.save(update_fields=["public_visible"])
    assert start(lane, status="working", project_id=lane.project.pk).account_project_id == lane.project.pk


@pytest.mark.parametrize("status", ["attending_event", "invented", "guest"])
def test_member_cannot_assign_event_or_guest_status(lane, status):
    with pytest.raises(PresenceError):
        start(lane, status=status)


def test_account_only_guest(lane):
    row = services.start_session(lane.guest, lane.space, 60, latitude=0, longitude=0)
    assert row.status == "guest" and row.membership_id is None and row.account == lane.guest
    with pytest.raises(PresenceError):
        services.start_session(lane.guest, lane.space, 60, status="working", latitude=0, longitude=0)


def test_revoked_member_is_not_reclassified_as_guest(lane):
    MakerspaceMembership.objects.filter(user=lane.owner, makerspace=lane.space).update(status="revoked")
    with pytest.raises(PresenceError):
        start(lane)


def test_staff_walk_in_uses_existing_scoped_identity(lane):
    walkin = lane.person("walkin")
    walkin.is_walk_in = True
    walkin.set_unusable_password()
    walkin.save(update_fields=["is_walk_in", "password"])
    row = services.staff_check_in(lane.staff, walkin, lane.space, 60)
    assert row.status == "guest" and row.account == walkin
    with pytest.raises(PresenceError):
        services.start_session(walkin, lane.space, 60, latitude=0, longitude=0)


def test_repeated_start_reuses_session_and_end_hides_it(lane):
    first, again = start(lane), start(lane)
    assert first.pk == again.pk
    services.end_session(lane.owner, lane.space)
    assert services.current_session(lane.owner, lane.space) is None


def test_renew_extends_from_now(lane, monkeypatch):
    row = start(lane)
    moment = row.started_at + timedelta(minutes=20)
    monkeypatch.setattr("apps.presence.services.timezone.now", lambda: moment)
    renewed = services.renew_session(lane.owner, lane.space, 120)
    assert renewed.pk == row.pk and renewed.expires_at == moment + timedelta(minutes=120)
    assert renewed.revision == 2


def test_historical_session_requires_new_geofenced_check_in(lane):
    row = start(lane)
    now = timezone.now()
    PresenceSession.objects.filter(pk=row.pk).update(started_at=now - timedelta(hours=2), expires_at=now - timedelta(hours=1))
    with pytest.raises(PresenceError) as error:
        services.renew_session(lane.owner, lane.space, 60)
    assert error.value.detail["code"] == "session_expired"


def test_account_alias_is_database_enforced(lane):
    row = start(lane)
    with transaction.atomic(), pytest.raises(IntegrityError):
        PresenceSession.objects.filter(pk=row.pk).update(account=lane.guest)


def test_module_off_and_tombstone_refuse_all_writes(lane, monkeypatch):
    lane.space.enabled_modules.remove("presence")
    lane.space.save(update_fields=["enabled_modules"])
    with pytest.raises(NotFound):
        start(lane)
    lane.space.enabled_modules.append("presence")
    lane.space.save(update_fields=["enabled_modules"])
    monkeypatch.setattr("apps.presence.policy.app_is_tombstoned", lambda *_: True)
    with pytest.raises(NotFound):
        services.staff_check_in(lane.staff, lane.owner, lane.space, 60)


def test_tenant_isolation(lane):
    foreign = Makerspace.objects.create(name="Foreign", slug="presence-foreign", enabled_modules=["presence"])
    with pytest.raises(PresenceError):
        services.staff_check_in(lane.staff, lane.owner, foreign, 60)
    row = start(lane)
    assert services.current_session(lane.owner, foreign) is None
    assert services.current_session(lane.guest, lane.space) is None
    assert services.current_session(lane.owner, lane.space).pk == row.pk


def test_module_purge_removes_presence_without_removing_memberships(lane):
    from apps.makerspaces.module_purge import purge_module
    from apps.presence.models import PresencePreference, PresenceSettings
    start(lane)
    lane.space.enabled_modules.remove("presence")
    lane.space.save(update_fields=["enabled_modules"])
    from apps.accounts.models import User
    operator = User.objects.create_superuser(username="presence-purge-operator", password=None)
    purge_module(lane.space, "presence", operator)
    assert not PresenceSession.objects.filter(makerspace=lane.space).exists()
    assert not PresenceSettings.objects.filter(makerspace=lane.space).exists()
    assert not PresencePreference.objects.filter(makerspace=lane.space).exists()
    assert MakerspaceMembership.objects.filter(makerspace=lane.space, user=lane.owner).exists()
