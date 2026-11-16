"""X29: per-space erasure requests. Approval anonymises this space's data; money and audit stay."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.makerspaces.membership_records import update_record
from apps.makerspaces.models import MembershipErasureRequest, MembershipRecord
from apps.payments.models import Payment
from tests.makerspaces.l4_helpers import features_off, features_on, member, space_with_manager
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _setup(slug):
    space, manager = space_with_manager(slug)
    features_on(space, "erasure", "records")
    membership = member(slug, space)
    return space, manager, membership


def test_member_asks_staff_approve_record_is_blanked_money_and_audit_kept():
    space, manager, membership = _setup("er-approve")
    update_record(manager, membership, {"state_code": "29", "gstin": "29ABCDE1234F1Z5", "staff_notes": "x"})
    from tests.payments.refund_case_helpers import membership_charge
    payment = membership_charge(space, membership.user)
    ask = authenticated_client(membership.user).post(
        reverse("member-erasure-requests", args=[space.pk]), {"note": "Moving away"}, format="json")
    assert ask.status_code == 201, ask.content
    again = authenticated_client(membership.user).post(reverse("member-erasure-requests", args=[space.pk]), {}, format="json")
    assert again.status_code == 400
    row = MembershipErasureRequest.objects.get(pk=ask.json()["id"])
    decided = authenticated_client(manager).post(reverse("admin-membership-erasure-approve", args=[row.pk]), {}, format="json")
    assert decided.status_code == 200, decided.content
    membership.refresh_from_db()
    record = MembershipRecord.objects.get(membership=membership)
    assert membership.status == "revoked"
    assert (record.gstin, record.staff_notes, record.state_code) == ("", "", "")
    assert Payment.objects.filter(pk=payment.pk).exists()
    assert membership.user.__class__.objects.filter(pk=membership.user_id).exists()  # account kept
    assert AuditLog.objects.filter(action="membership.erasure_approved").exists()
    row.refresh_from_db()
    assert row.member_note == ""


def test_reject_needs_a_note_and_member_can_withdraw():
    space, manager, membership = _setup("er-reject")
    url = reverse("member-erasure-requests", args=[space.pk])
    first = authenticated_client(membership.user).post(url, {}, format="json").json()
    reject = reverse("admin-membership-erasure-reject", args=[first["id"]])
    assert authenticated_client(manager).post(reject, {"note": ""}, format="json").status_code == 400
    assert authenticated_client(manager).post(reject, {"note": "Open loan first"}, format="json").status_code == 200
    second = authenticated_client(membership.user).post(url, {}, format="json").json()
    withdraw = reverse("member-erasure-request-withdraw", args=[space.pk, second["id"]])
    assert authenticated_client(membership.user).post(withdraw).json()["status"] == "withdrawn"
    membership.refresh_from_db()
    assert membership.status == "active"


def test_off_switch_is_a_404_and_keeps_requests():
    space, manager, membership = _setup("er-off")
    authenticated_client(membership.user).post(reverse("member-erasure-requests", args=[space.pk]), {}, format="json")
    features_off(space, "erasure")
    assert authenticated_client(membership.user).get(reverse("member-erasure-requests", args=[space.pk])).status_code == 404
    assert authenticated_client(manager).get(reverse("admin-membership-erasure-requests", args=[space.pk])).status_code == 404
    assert MembershipErasureRequest.objects.count() == 1
