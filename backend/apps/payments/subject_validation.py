"""Ownership checks for admission charges, including preserved orphan receipts."""

from django.core.exceptions import ValidationError


def validate_membership_request(payment, identity_unchanged):
    from apps.makerspaces.models import MembershipRequest

    request = MembershipRequest.objects.filter(
        pk=payment.subject_id, makerspace_id=payment.makerspace_id,
    ).only("user_id").first()
    if request is None and not identity_unchanged:
        raise ValidationError({
            "subject_id": "Payment subject must belong to the payment makerspace.",
        })
    if request is not None and (request.user_id is None or payment.member_id != request.user_id):
        raise ValidationError({"member": "Payment member must be the applicant."})


def validate_subject(payment, identity_unchanged):
    """Every subject must belong to the payment's makerspace (and its member)."""
    from apps.payments.models_payment import Payment

    if payment.subject_type == Payment.SubjectType.MEMBERSHIP_REQUEST:
        validate_membership_request(payment, identity_unchanged)
    if payment.subject_type == Payment.SubjectType.MACHINE_SERVICE_REQUEST and payment.subject_id:
        from apps.machines.models import MachineServiceRequest

        if not identity_unchanged and not MachineServiceRequest.objects.filter(
            pk=payment.subject_id,
            makerspace_id=payment.makerspace_id,
        ).exists():
            raise ValidationError({"subject_id": "Payment subject must belong to the payment makerspace."})
    if payment.subject_type == Payment.SubjectType.BOOKING and payment.subject_id:
        from apps.bookings.models import Booking

        if not identity_unchanged:
            booking_exists = Booking.objects.filter(
                pk=payment.subject_id,
                space__makerspace_id=payment.makerspace_id,
            ).exists()
            if not booking_exists:
                raise ValidationError(
                    {"subject_id": "Payment subject must belong to the payment makerspace."}
                )
    if payment.subject_type == Payment.SubjectType.EVENT_REGISTRATION and payment.subject_id:
        from apps.events.models import EventRegistration

        if not identity_unchanged:
            registration_exists = EventRegistration.objects.filter(
                pk=payment.subject_id,
                event__makerspace_id=payment.makerspace_id,
            ).exists()
            if not registration_exists:
                raise ValidationError(
                    {"subject_id": "Payment subject must belong to the payment makerspace."}
                )
    if payment.subject_type in Payment.LOAN_SUBJECT_TYPES and payment.subject_id:
        from apps.hardware_requests.models import HardwareRequest

        if not identity_unchanged and not HardwareRequest.objects.filter(
            pk=payment.subject_id,
            makerspace_id=payment.makerspace_id,
        ).exists():
            raise ValidationError({"subject_id": "Payment subject must belong to the payment makerspace."})
    if payment.subject_type == Payment.SubjectType.MEMBERSHIP_TERM and payment.subject_id:
        from apps.makerspaces.models import MembershipTerm

        if not identity_unchanged and not MembershipTerm.objects.filter(
            pk=payment.subject_id,
            membership__makerspace_id=payment.makerspace_id,
        ).exists():
            raise ValidationError({"subject_id": "Payment subject must belong to the payment makerspace."})
    if payment.subject_type == Payment.SubjectType.MAKERSPACE_MEMBERSHIP and payment.subject_id:
        from apps.makerspaces.models import MakerspaceMembership

        membership = MakerspaceMembership.objects.filter(
            pk=payment.subject_id,
            makerspace_id=payment.makerspace_id,
        ).only("user_id").first()
        if membership is None and not identity_unchanged:
            raise ValidationError(
                {"subject_id": "Payment subject must belong to the payment makerspace."}
            )
        if membership is not None and payment.member_id != membership.user_id:
            raise ValidationError(
                {"member": "Payment member must be the membership user."}
            )
