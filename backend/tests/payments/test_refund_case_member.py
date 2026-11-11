"""Member requests: own settled charges only, one at a time, withdrawable while open."""

import pytest
from django.urls import reverse

from apps.accounts.account_deletion_blockers import collect
from apps.audit.models import AuditLog
from apps.payments.models import Refund, RefundCase
from apps.payments.services_refund_cases import open_due_case
from tests.payments.refund_case_helpers import charge, deposit, member, paid_event, registration, space_with_currency
from tests.return_helpers import authenticated_client, make_member

pytestmark = pytest.mark.django_db


def ask(user, payment, reason="Could not attend"):
    url = reverse("member-refund-request", args=[payment.makerspace_id, payment.pk])
    return authenticated_client(user).post(url, {"reason": reason}, format="json")


def withdraw(user, space, case_id):
    url = reverse("member-refund-withdraw", args=[space.pk, case_id])
    return authenticated_client(user).post(url, {}, format="json")


def history(user, space):
    return authenticated_client(user).get(reverse("member-payment-history", args=[space.pk])).data


def test_request_then_duplicate_then_withdraw_and_history_tracks_it():
    space = space_with_currency("mem-request")
    user = member("mem-request-m", space)
    payment = charge(space, user, subject_id=registration(paid_event(space), user).pk)
    assert history(user, space)[0]["refund_requestable"] is True
    created = ask(user, payment)
    assert created.status_code == 201 and created.data["withdrawable"] is True
    case = RefundCase.objects.get()
    assert (case.kind, case.requested_by, case.member_reason) == ("request", user, "Could not attend")
    dup = ask(user, payment)
    assert dup.status_code == 409 and dup.data["code"] == "refund_request_exists"
    row = history(user, space)[0]
    assert row["refund_case"]["status"] == "open" and row["refund_requestable"] is False
    assert "member_reason" not in row["refund_case"] and "policy_snapshot" not in row["refund_case"]
    assert withdraw(user, space, case.pk).data["status"] == "withdrawn"
    assert history(user, space)[0]["refund_requestable"] is True
    assert AuditLog.objects.filter(action="payment.refund_case_withdrawn").exists()
    assert not Refund.objects.exists()


def test_due_assessment_absorbs_the_request_and_cannot_be_withdrawn():
    space = space_with_currency("mem-due")
    user = member("mem-due-m", space)
    payment = charge(space, user, subject_id=registration(paid_event(space), user).pk)
    case = open_due_case(payment, reason_code="event_cancelled", actor=None)
    response = ask(user, payment, "Please refund to card")
    assert response.status_code == 201 and response.data["id"] == case.pk and response.data["kind"] == "due"
    assert RefundCase.objects.get().member_reason == "Please refund to card"
    assert ask(user, payment).status_code == 409
    blocked = withdraw(user, space, case.pk)
    assert blocked.status_code == 409 and blocked.data["code"] == "refund_case_not_withdrawable"


@pytest.mark.parametrize("kind,status,code", [
    ("loan_deposit", "paid_offline", "refund_request_not_allowed"),
    ("event_registration", "pending", "refund_not_settled"),
    ("event_registration", "waived", "refund_not_settled"),
])
def test_deposits_and_unpaid_charges_cannot_be_requested(kind, status, code):
    space = space_with_currency(f"mem-refuse-{kind}-{status}")
    user = member(f"mem-refuse-{kind}-{status}", space)
    if kind == "loan_deposit":
        payment = deposit(space, user)
        user = payment.member
    else:
        payment = charge(space, user, subject_id=registration(paid_event(space), user).pk, status=status)
    response = ask(user, payment)
    assert response.status_code == 400 and response.data["code"] == code
    assert not RefundCase.objects.exists()


def test_other_members_and_foreign_routes_get_404():
    space = space_with_currency("mem-foreign")
    owner, other = member("mem-foreign-owner", space), member("mem-foreign-other", space)
    payment = charge(space, owner, subject_id=registration(paid_event(space), owner).pk)
    assert ask(other, payment).status_code == 404
    ask(owner, payment)
    case = RefundCase.objects.get()
    assert withdraw(other, space, case.pk).status_code == 404
    staff = make_member("mem-foreign-staff", space)
    assert withdraw(staff, space, case.pk).status_code in {403, 404}
    assert ask(owner, payment, "").status_code == 400


def test_an_undecided_refund_blocks_account_deletion():
    space = space_with_currency("mem-delete")
    user = member("mem-delete-m", space)
    payment = charge(space, user, subject_id=registration(paid_event(space), user).pk)
    ask(user, payment)
    codes = {row["code"] if isinstance(row, dict) else getattr(row, "code", None) for row in collect(user)}
    assert "refund_under_review" in codes
