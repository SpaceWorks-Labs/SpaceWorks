"""access.authorize reason codes, credentials (digests, lockout), usage idempotency, and staff-only calibration."""
import time
import uuid

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.devices.models import AdapterAccessLog, AdapterCredential, AdapterUsageLog
from apps.inventory.models import InventoryProduct
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member

pytestmark = pytest.mark.django_db(transaction=True)


def _credential(case, user, kind="nfc", secret="04A1B2C3D4"):
    url = reverse("devices:admin-adapter-credentials", args=[case["space"].pk])
    return case["client"].post(url, {"user_id": user.pk, "kind": kind, "secret": secret}, format="json")


def _authorize(case, credential):
    return case["sim"].post("access/authorize", {"binding_id": case["binding_id"], "credential": credential})


def test_an_unknown_credential_is_denied_with_a_reason_and_logged():
    case = adapter_case("ac-unknown")
    response = _authorize(case, {"type": "nfc", "value": "DEADBEEF"})
    assert response.status_code == 200
    assert response.data["allowed"] is False and response.data["reason"] == "unknown_credential"
    assert AdapterAccessLog.objects.filter(reason="unknown_credential", allowed=False).count() == 1


def test_a_restricted_member_is_denied_member_restricted():
    case = adapter_case("ac-restricted")
    member = plain_member("ac-restricted-m", case["space"])
    assert _credential(case, member).status_code == 201
    User.objects.filter(pk=member.pk).update(access_status="restricted")
    response = _authorize(case, {"type": "nfc", "value": "04A1B2C3D4"})
    assert response.data["allowed"] is False and response.data["reason"] == "member_restricted"


def test_credentials_are_stored_as_digests_only_and_never_echoed():
    case = adapter_case("ac-digest")
    member = plain_member("ac-digest-m", case["space"])
    created = _credential(case, member, secret="04A1B2C3D4")
    assert "secret" not in created.data and "digest" not in created.data
    row = AdapterCredential.objects.get(pk=created.data["id"])
    assert "04A1B2C3D4" not in row.digest and len(row.digest) == 64
    listed = case["client"].get(reverse("devices:admin-adapter-credentials", args=[case["space"].pk]))
    assert "04A1B2C3D4" not in str(listed.data)


def test_a_pin_locks_after_five_wrong_attempts():
    # Decision 336j: the lock still happens after five wrong PINs, but silently: every member-level failure answers
    # the same `unknown_credential`, so a keypad cannot tell a locked PIN from a wrong one or a missing one.
    case = adapter_case("ac-pin")
    member = plain_member("ac-pin-m", case["space"])
    assert _credential(case, member, kind="pin", secret="482913").status_code == 201
    from apps.makerspaces.models import MemberCard
    number = MemberCard.objects.filter(makerspace=case["space"], membership__user=member).first()
    if number is None:
        pytest.skip("fixture member has no member card; PIN lockout is covered once a card exists")
    body = {"type": "pin", "value": "000000", "member_number": str(number.card_number)}
    reasons = [_authorize(case, body).data["reason"] for _ in range(5)]
    assert reasons == ["unknown_credential"] * 5
    assert AdapterCredential.objects.get(user=member, kind="pin").locked_until is not None
    assert _authorize(case, {**body, "value": "482913"}).data["reason"] == "unknown_credential"


def test_a_door_admits_an_active_member_and_refuses_a_lapsed_one():
    case = adapter_case("ac-door", caps=("status", "events"), extra=("access.authorize", "door.access"))
    from django.urls import reverse as rev
    door = case["client"].post(rev("devices:admin-adapter-binding-create", args=[case["device"].pk]), {
        "target_type": "door", "external_ref": "front", "capabilities": ["access.authorize", "door.access"]},
        format="json")
    assert door.status_code == 201, door.data
    member = plain_member("ac-door-m", case["space"])
    assert _credential(case, member).status_code == 201
    body = {"binding_id": door.data["id"], "credential": {"type": "nfc", "value": "04A1B2C3D4"}}
    assert case["sim"].post("access/authorize", body).data["allowed"] is True
    from apps.makerspaces.models import MakerspaceMembership
    MakerspaceMembership.objects.filter(makerspace=case["space"], user=member).update(status="revoked")
    assert case["sim"].post("access/authorize", body).data["reason"] == "membership_required"


def test_usage_log_is_idempotent_by_operation_id():
    case = adapter_case("ac-usage")
    now = int(time.time())
    body = {"operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"], "started_at": now - 600,
            "ended_at": now, "active_minutes": 8, "idle_minutes": 2, "outcome": "completed"}
    assert case["sim"].post("usage", body).data["result"] == "stored"
    assert case["sim"].post("usage", body).data["result"] == "duplicate"
    assert AdapterUsageLog.objects.count() == 1
    bad = case["sim"].post("usage", {**body, "operation_id": str(uuid.uuid4()), "ended_at": now - 900})
    assert bad.status_code == 400


def _pointer_case(slug):
    case = adapter_case(slug, caps=("status", "events"), extra=("locate.calibrate", "locate.indicate"))
    shelf = case["client"].post(reverse("devices:admin-adapter-binding-create", args=[case["device"].pk]), {
        "target_type": "space", "external_ref": "shelf-wall", "capabilities": ["locate.calibrate", "locate.indicate"]},
        format="json")
    assert shelf.status_code == 201, shelf.data
    return case, shelf.data["id"]


def test_calibration_is_staff_only_and_the_pose_never_leaves_staff_surfaces():
    case, binding = _pointer_case("lo-staff")
    product = InventoryProduct.objects.create(makerspace=case["space"], name="Resistors", storage_location="Shelf A")
    pose = {"pan": 12.5, "tilt": -3}
    saved = case["client"].put(reverse("devices:admin-adapter-poses", args=[binding]),
                               {"target_type": "storage_location", "target_id": "Shelf A", "pose": pose},
                               format="json")
    assert saved.status_code == 200, saved.data
    member = plain_member("lo-staff-m", case["space"])
    other = APIClient()
    other.force_authenticate(member)
    assert other.get(reverse("devices:admin-adapter-poses", args=[binding])).status_code in (403, 404)
    assert other.put(reverse("devices:admin-adapter-poses", args=[binding]),
                     {"target_type": "storage_location", "target_id": "Shelf A", "pose": pose},
                     format="json").status_code in (403, 404)
    # the adapter's own binding list and the command log never carry the pose
    assert "pan" not in str(case["sim"].get("bindings").data)
    cmds = case["client"].get(reverse("devices:admin-adapter-commands", args=[case["device"].pk]))
    assert "pan" not in str(cmds.data) and product.pk


def test_indicate_needs_a_calibrated_pose_and_a_real_target():
    case, binding = _pointer_case("lo-indicate")
    InventoryProduct.objects.create(makerspace=case["space"], name="Bolts", storage_location="Shelf B")
    url = reverse("devices:admin-adapter-indicate", args=[binding])
    body = {"mode": "point", "target_type": "storage_location", "target_id": "Shelf B"}
    assert case["client"].post(url, body, format="json").status_code == 409  # not calibrated yet
    assert case["client"].post(url, {**body, "target_id": "Nowhere"}, format="json").status_code == 404
    case["client"].put(reverse("devices:admin-adapter-poses", args=[binding]),
                       {"target_type": "storage_location", "target_id": "Shelf B", "pose": {"pan": 1}}, format="json")
    done = case["client"].post(url, body, format="json")
    assert done.status_code == 201, done.data
    leased = case["sim"].post("commands/lease").data["command"]
    assert leased["capability"] == "locate.indicate" and leased["params"]["pose"] == {"pan": 1}
