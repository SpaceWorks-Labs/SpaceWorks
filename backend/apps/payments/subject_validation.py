"""Per-subject ownership checks for `Payment.clean()`, including preserved orphan receipts.

Each check answers one question: does the polymorphic `subject_id` name a row owned by the
payment's makerspace? A missing subject is legitimate only for a saved row whose subject
identity is unchanged (its subject was purged); `identity_unchanged` carries that fact.
"""

from django.core.exceptions import ValidationError

FOREIGN_SUBJECT = "Payment subject must belong to the payment makerspace."


def _refuse_foreign():
    raise ValidationError({"subject_id": FOREIGN_SUBJECT})


def validate_membership_request(payment, identity_unchanged):
    from apps.makerspaces.models import MembershipRequest

    request = MembershipRequest.objects.filter(
        pk=payment.subject_id, makerspace_id=payment.makerspace_id,
    ).only("user_id").first()
    if request is None and not identity_unchanged:
        _refuse_foreign()
    if request is not None and (request.user_id is None or payment.member_id != request.user_id):
        raise ValidationError({"member": "Payment member must be the applicant."})


def _machine_service_request(payment):
    from apps.machines.models import MachineServiceRequest

    return MachineServiceRequest.objects.filter(
        pk=payment.subject_id, makerspace_id=payment.makerspace_id,
    ).exists()


def _booking(payment):
    from apps.bookings.models import Booking

    return Booking.objects.filter(
        pk=payment.subject_id, space__makerspace_id=payment.makerspace_id,
    ).exists()


def _event_registration(payment):
    from apps.events.models import EventRegistration

    return EventRegistration.objects.filter(
        pk=payment.subject_id, event__makerspace_id=payment.makerspace_id,
    ).exists()


def _hardware_request(payment):
    from apps.hardware_requests.models import HardwareRequest

    return HardwareRequest.objects.filter(
        pk=payment.subject_id, makerspace_id=payment.makerspace_id,
    ).exists()


def _membership_term(payment):
    from apps.makerspaces.models import MembershipTerm

    return MembershipTerm.objects.filter(
        pk=payment.subject_id, membership__makerspace_id=payment.makerspace_id,
    ).exists()


def validate_makerspace_membership(payment, identity_unchanged):
    from apps.makerspaces.models import MakerspaceMembership

    membership = MakerspaceMembership.objects.filter(
        pk=payment.subject_id, makerspace_id=payment.makerspace_id,
    ).only("user_id").first()
    if membership is None and not identity_unchanged:
        _refuse_foreign()
    if membership is not None and payment.member_id != membership.user_id:
        raise ValidationError({"member": "Payment member must be the membership user."})


#: subject_type -> "does the subject exist in the payment's makerspace?"
OWNER_CHECKS = {
    "machine_service_request": _machine_service_request,
    "booking": _booking,
    "event_registration": _event_registration,
    "loan_deposit": _hardware_request,
    "loan_late_fee": _hardware_request,
    "membership_term": _membership_term,
}


def validate_subject(payment, identity_unchanged):
    """Run the ownership check for `payment.subject_type`; called from `Payment.clean()`."""
    subject_type = payment.subject_type
    if subject_type == "membership_request":
        validate_membership_request(payment, identity_unchanged)
        return
    if not payment.subject_id:
        return
    if subject_type == "makerspace_membership":
        validate_makerspace_membership(payment, identity_unchanged)
        return
    check = OWNER_CHECKS.get(subject_type)
    if check is not None and not identity_unchanged and not check(payment):
        _refuse_foreign()
