"""Who may report a problem, and with what (#103).

Only the people who USED the thing: the borrower of that loan, the booker of that
booking, the owner of that machine job. A member is matched by account; in a space
without member accounts the borrower (or a guest booker) is matched by the email they
proved with the one-time code (#80). Anything else is `reporter_not_eligible`, and an id
outside this space reads exactly like one that does not exist.
"""

from django.db.models import Q
from rest_framework.exceptions import ValidationError

from . import errors

LOAN_STATES = ("issued", "partially_returned", "returned", "closed_with_issue")
BOOKING_STATES = ("confirmed", "completed", "no_show")


def _loan(space, pk, member, email_key):
    from apps.hardware_requests.models import HardwareRequest
    loan = HardwareRequest.objects.filter(makerspace=space, pk=pk).first()
    if loan is None or loan.status not in LOAN_STATES:
        raise errors.not_eligible()
    by_member = member is not None and loan.requester_id == member.pk
    by_email = bool(email_key) and loan.anonymous_payload_fingerprint == email_key
    if not (by_member or by_email):
        raise errors.not_eligible()
    return loan


def loan_subject(space, loan_id, *, member=None, email_key=None, product_id=None, asset_id=None):
    from apps.hardware_requests.models import HardwareRequestItemAsset
    loan = _loan(space, loan_id, member, email_key)
    items = list(loan.items.select_related("product"))
    if asset_id:
        link = HardwareRequestItemAsset.objects.filter(request_item__request=loan, asset_id=asset_id).select_related(
            "asset__product").first()
        if link is None:
            raise ValidationError({"asset_id": "That unit was not part of this loan."})
        return loan, "inventory_asset", link.asset
    if product_id is None and len(items) == 1:
        return loan, "inventory_product", items[0].product
    match = next((item.product for item in items if item.product_id == product_id), None)
    if match is None:
        raise ValidationError({"product_id": "Choose an item that was part of this loan."})
    return loan, "inventory_product", match


def booking_subject(space, booking_id=None, *, token=None, member=None, email=None):
    from apps.bookings.models import Booking
    from apps.hardware_requests.contact_verification import normalize_email
    lookup = {"public_token": token} if token else {"pk": booking_id}
    booking = Booking.objects.select_related("space").filter(space__makerspace=space, **lookup).first()
    if booking is None or booking.status not in BOOKING_STATES:
        raise errors.not_eligible()
    by_member = member is not None and booking.member_id == member.pk
    by_email = bool(email) and booking.member_id is None and normalize_email(booking.email) == normalize_email(email)
    if not (by_member or by_email):
        raise errors.not_eligible()
    return booking, "bookable_space", booking.space


def job_subject(space, job_id, *, member):
    from apps.machines.models import MachineServiceRequest
    job = (MachineServiceRequest.objects.select_related("assigned_machine", "bucket__machine")
           .filter(Q(makerspace=space), pk=job_id).first())
    if job is None or member is None or job.member_id != member.pk:
        raise errors.not_eligible()
    machine = job.assigned_machine or getattr(job.bucket, "machine", None)
    if machine is None:
        raise ValidationError({"machine_job_id": "This job has not been on a machine yet."})
    return job, "machine", machine
