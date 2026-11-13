"""MOD-3 flow audit: the geofence decision and the presence row's identity rules, branch by branch."""
import pytest
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.presence.geofence import (
    ACCURACY_CEILING_M, evaluate_geofence, geofence_metadata, haversine_distance_m, require_inside,
)
from apps.presence.models import PresenceSession
from apps.presence.policy import PresenceError
from .fence_helpers import fence

pytestmark = pytest.mark.django_db


def _space(slug, radius=100):
    return fence(Makerspace.objects.create(name=slug, slug=slug), radius_m=radius)


def test_the_check_is_skipped_when_the_feature_or_the_fence_is_off():
    space = Makerspace.objects.create(name="Off", slug="mod3-geo-off")
    assert evaluate_geofence(space, latitude=0, longitude=0, accuracy=1) is None
    fenced = _space("mod3-geo-switch")
    Makerspace.objects.filter(pk=fenced.pk).update(enabled_features=[])
    fenced.refresh_from_db()
    assert evaluate_geofence(fenced, latitude=0, longitude=0, accuracy=1) is None
    Makerspace.objects.filter(pk=fenced.pk).update(enabled_features=["presence.geofence"], geofence_enabled=False)
    fenced.refresh_from_db()
    assert evaluate_geofence(fenced, latitude=0, longitude=0, accuracy=1) is None


@pytest.mark.parametrize("latitude,longitude,accuracy", [(None, 0, 1), (0, None, 1), (0, 0, None),
                                                          (float("nan"), 0, 1), (0, float("inf"), 1), (0, 0, float("-inf"))])
def test_missing_or_non_finite_readings_are_reported_as_missing_coordinates(latitude, longitude, accuracy):
    result = evaluate_geofence(_space("mod3-geo-missing"), latitude=latitude, longitude=longitude, accuracy=accuracy)
    assert (result.in_range, result.reason, result.distance_m, result.accuracy_m) == (None, "missing_coordinates", None, None)


def test_accuracy_ceiling_is_inclusive_at_50_and_refused_at_just_above():
    space = _space("mod3-geo-acc")
    at = evaluate_geofence(space, latitude=0, longitude=0, accuracy=ACCURACY_CEILING_M)
    above = evaluate_geofence(space, latitude=0, longitude=0, accuracy=ACCURACY_CEILING_M + 0.01)
    assert (at.in_range, at.reason) == (True, None)
    assert (above.in_range, above.reason) == (False, "low_accuracy")


def test_the_radius_boundary_is_inclusive_by_whole_metres():
    longitude = 0.0009  # roughly 100 m at the equator
    metres = haversine_distance_m(0, 0, 0, longitude)
    assert 99 < metres < 101
    inside = evaluate_geofence(_space("mod3-geo-in", radius=int(metres) + 1), latitude=0, longitude=longitude, accuracy=5)
    outside = evaluate_geofence(_space("mod3-geo-out", radius=int(metres) - 1), latitude=0, longitude=longitude, accuracy=5)
    assert (inside.in_range, inside.reason) == (True, None)
    assert (outside.in_range, outside.reason) == (False, "out_of_range")


@pytest.mark.parametrize("kwargs,code", [
    ({}, "location_required"), ({"latitude": 0}, "location_required"),
    ({"latitude": True, "longitude": 0}, "location_invalid"), ({"latitude": "0", "longitude": 0}, "location_invalid"),
    ({"latitude": float("nan"), "longitude": 0}, "location_invalid"), ({"latitude": 91, "longitude": 0}, "location_invalid"),
    ({"latitude": 0, "longitude": -181}, "location_invalid"), ({"latitude": 0, "longitude": 0, "accuracy": -1}, "location_invalid"),
    ({"latitude": 0, "longitude": 0, "accuracy": 51}, "location_inaccurate"),
    ({"latitude": 0, "longitude": 0.01, "accuracy": 5}, "outside_geofence"),
])
def test_require_inside_refuses_each_bad_reading_with_its_own_code(kwargs, code):
    with pytest.raises(PresenceError) as raised:
        require_inside(_space(f"mod3-geo-{code}-{len(kwargs)}-{abs(hash(str(kwargs))) % 9999}"), **kwargs)
    assert raised.value.detail["code"] == code and raised.value.status_code == 400


def test_require_inside_accepts_the_centre_and_a_missing_accuracy_as_zero():
    require_inside(_space("mod3-geo-ok"), latitude=0, longitude=0)
    require_inside(_space("mod3-geo-ok2"), latitude=0, longitude=0, accuracy=0)


def test_an_unconfigured_space_refuses_self_check_in_outright():
    with pytest.raises(PresenceError) as raised:
        require_inside(Makerspace.objects.create(name="Plain", slug="mod3-geo-plain"), latitude=0, longitude=0)
    assert raised.value.detail["code"] == "geofence_unconfigured"


@pytest.mark.parametrize("distance,bucket", [(0, "0-10m"), (10, "0-10m"), (10.5, "11-25m"), (25, "11-25m"), (26, "26-50m"), (50, "26-50m"), (51, "50m+")])
def test_distance_and_accuracy_are_only_ever_stored_as_buckets(distance, bucket):
    from apps.presence.geofence import GeofenceResult
    meta = geofence_metadata(GeofenceResult(in_range=False, reason="out_of_range", distance_m=distance, accuracy_m=distance))
    assert meta == {"geofence_checked": True, "in_range": False, "reason": "out_of_range",
                    "distance_bucket": bucket, "accuracy_bucket": bucket}
    assert geofence_metadata(None) == {}
    assert geofence_metadata(GeofenceResult(True, None, None, None)) == {"geofence_checked": True, "in_range": True}


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@example.test", password="password")


def test_a_presence_row_mirrors_account_and_member_and_rejects_a_foreign_membership():
    space, other = _space("mod3-row-a"), _space("mod3-row-b")
    user, stranger = _user("mod3-row-user"), _user("mod3-row-stranger")
    role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    mine = MakerspaceMembership.objects.create(makerspace=space, user=user, assigned_role=role, role="custom", status="active")
    from datetime import timedelta
    from django.utils import timezone
    now = timezone.now()
    row = PresenceSession.objects.create(makerspace=space, member=user, started_at=now, expires_at=now + timedelta(hours=1))
    assert row.account_id == user.pk  # account filled from the legacy member field
    row2 = PresenceSession.objects.create(makerspace=space, account=user, started_at=now, expires_at=now + timedelta(hours=1))
    assert row2.member_id == user.pk  # and the other way round
    row2.account_id = stranger.pk
    with pytest.raises(ValidationError):
        row2.clean()  # account and member must agree
    row2.account_id = user.pk
    row2.membership = mine
    row2.makerspace = other
    with pytest.raises(ValidationError):
        row2.clean()  # membership belongs to a different makerspace
