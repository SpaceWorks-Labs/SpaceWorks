"""#163A approver: the Space Manager or a finance admin decides a difference case; nobody else, nothing automatic."""

import pytest
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.payments.models import Refund, RefundCase
from apps.payments.services_refund_cases import open_due_case
from apps.payments.services_refund_decisions import approve_case, decline_case
from tests.l24_local.helpers import D, client, l24_space
from tests.payments.refund_case_helpers import base, booking, finance_reader, member, receipt, receipt_payload
from tests.rbac_f6_helpers import custom_actor
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db
A = rbac.Action


def finance_admin(space, name="finance"):
    """view_finance plus record_payment, and no area role: only an organization grant says that."""
    from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
    user = make_user(f"{space.slug}-{name}", access_status="active")
    organization = Organization.objects.create(name="Finance office", slug=f"fin-{space.pk}-{user.pk}")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=space, relationship="owner")
    OrganizationMembership.objects.create(organization=organization, user=user,
                                          granted_actions=[A.VIEW_FINANCE, A.RECORD_PAYMENT])
    return user


def dropped(slug):
    space, sm = l24_space(slug, modules=("bookings",))
    row, payment = booking(space, member(f"{slug}-m", space), amount="30.00")
    url = reverse("admin-bookable-space-detail", kwargs={"pk": row.space_id})
    assert client(sm).patch(url, {"payment_amount": "20.00"}, format="json").status_code == 200
    return space, sm, RefundCase.objects.get(payment=payment)


def test_the_area_manager_cannot_decide_a_price_drop_case():
    space, _, case = dropped("l24-ap-area")
    manager = custom_actor(space, [A.MANAGE_BOOKINGS], name="booker")  # the Booking Manager role
    with pytest.raises(PermissionDenied):
        approve_case(case, actor=manager, receipt=receipt())
    with pytest.raises(PermissionDenied):
        decline_case(case, actor=manager, note="no")
    assert RefundCase.objects.get(pk=case.pk).status == "open" and not Refund.objects.exists()


def test_a_finance_reader_without_record_payment_cannot_decide_either():
    space, _, case = dropped("l24-ap-reader")
    reader = finance_reader(space)
    with pytest.raises(PermissionDenied):
        decline_case(case, actor=reader, note="no")


def test_a_finance_admin_approves_and_only_then_money_moves():
    space, _, case = dropped("l24-ap-finance")
    finance = finance_admin(space)
    response = client(finance).post(f"{base(space)}/refund-cases/{case.pk}/approve",
                                    {"receipt": receipt_payload()}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["needs_finance_approval"] is True and response.data["status"] == "approved"
    refund = Refund.objects.get()
    assert refund.amount == D("10.00") and refund.payment_id == case.payment_id


def test_the_space_manager_may_decline():
    space, sm, case = dropped("l24-ap-sm")
    declined = decline_case(case, actor=sm, note="Already discounted at the desk")
    assert declined.status == "declined" and not Refund.objects.exists()


def test_ordinary_cancellation_cases_keep_their_area_authority():
    space, _ = l24_space("l24-ap-plain", modules=("bookings",))
    row, payment = booking(space, member("l24-ap-plain-m", space), amount="30.00")
    case = open_due_case(payment, reason_code="staff_cancelled", actor=None)
    manager = custom_actor(space, [A.MANAGE_BOOKINGS], name="booker")
    # A Booking Manager decides an ordinary cancellation case (declining needs no record_payment).
    assert decline_case(case, actor=manager, note="Rebooked instead").status == "declined"
