"""`Payment.clean()` for the lane L18 subjects: the subject is this space's, the payer its giver."""

from django.core.exceptions import ValidationError


def validate_gift_subject(payment, identity_unchanged):
    from .models import Donation, SponsorshipCharge

    if payment.subject_type == "donation":
        row = Donation.objects.filter(pk=payment.subject_id, makerspace_id=payment.makerspace_id).values(
            "donor_id").first()
        owner = row["donor_id"] if row else None
    else:
        row = SponsorshipCharge.objects.filter(pk=payment.subject_id, makerspace_id=payment.makerspace_id).values(
            "pk").first()
        owner = None
    if row is None and not identity_unchanged:
        raise ValidationError({"subject_id": "Payment subject must belong to the payment makerspace."})
    if row is not None and payment.member_id != owner:
        raise ValidationError({"member": "Payment member must be the giver."})
