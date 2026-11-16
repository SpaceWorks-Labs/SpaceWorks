"""Lane F fixtures with separate staff and account-only payer identities."""

from apps.payments.models import Payment
from tests.return_helpers import make_accepted_request, make_member, make_product, make_space


def pending_charge(slug, *, provider="stripe", **overrides):
    space = make_space(slug)
    space.enabled_features = sorted(set(space.enabled_features) | {"billing.documents"})
    space.save(update_fields=["enabled_features"])
    staff = make_member(f"{slug}-manager", space)
    loan = make_accepted_request(space, make_product(space), 1)
    fields = {
        "makerspace": space, "member": loan.requester, "created_by": staff,
        "subject_type": Payment.SubjectType.LOAN_DEPOSIT, "subject_id": loan.pk,
        "subject_label": "Tool deposit", "amount": "10.00", "currency": "usd",
        "provider": provider,
    }
    fields.update(overrides)
    return space, staff, Payment.objects.create(**fields)
