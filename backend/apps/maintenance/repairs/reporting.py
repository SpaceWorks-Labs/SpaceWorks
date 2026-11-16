"""Who may report a problem, and with what (#103).

Only the people who USED the thing: the borrower of that loan, the booker of that
booking, the owner of that machine job, the member of that machine session. A member is matched by account; in a space
without member accounts the borrower (or a guest booker) is matched by the email they
proved with the one-time code (#80). Anything else is `reporter_not_eligible`, and an id
outside this space reads exactly like one that does not exist.
"""

from django.utils.translation import gettext
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.makerspaces.platform import feature_enabled

from . import errors

MACHINE_REPORTING = "machines.issue_reporting"
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
            raise ValidationError({"asset_id": gettext("That unit was not part of this loan.")})
        return loan, "inventory_asset", link.asset
    if product_id is None and len(items) == 1:
        return loan, "inventory_product", items[0].product
    match = next((item.product for item in items if item.product_id == product_id), None)
    if match is None:
        raise ValidationError({"product_id": gettext("Choose an item that was part of this loan.")})
    return loan, "inventory_product", match


def booking_subject(space, booking_id=None, *, token=None, member=None, email=None):
    from apps.bookings.models import Booking
    from apps.hardware_requests.contact_verification import normalize_email
    lookup = {"public_token": token} if token else {"pk": booking_id}
    booking = Booking.objects.select_related("space", "space__machine").filter(space__makerspace=space, **lookup).first()
    if booking is None or booking.status not in BOOKING_STATES:
        raise errors.not_eligible()
    by_member = member is not None and booking.member_id == member.pk
    by_email = bool(email) and booking.member_id is None and normalize_email(booking.email) == normalize_email(email)
    if not (by_member or by_email):
        raise errors.not_eligible()
    machine = booking.space.machine if booking.space.machine_id else None
    if machine is not None and machine.makerspace_id == space.pk and feature_enabled(space, MACHINE_REPORTING):
        # A booking of one machine's time reports a problem with THAT machine, so it reaches
        # the machine's type-scoped manager and the machine repair flow, not the room desk.
        return booking, "machine", machine
    return booking, "bookable_space", booking.space


def job_subject(space, job_id, *, member):
    from apps.machines.models import MachineServiceRequest
    job = (MachineServiceRequest.objects.select_related("assigned_machine", "bucket__machine")
           .filter(Q(makerspace=space), pk=job_id).first())
    if job is None or member is None or job.member_id != member.pk:
        raise errors.not_eligible()
    machine = job.assigned_machine or getattr(job.bucket, "machine", None)
    if machine is None:
        raise ValidationError({"machine_job_id": gettext("This job has not been on a machine yet.")})
    return job, "machine", machine


def session_subject(space, session_id, *, member):
    """Decision 220(d)2: the member's own machine session reports on its machine, while
    `machines.sessions` is on (`machines.issue_reporting` is checked when the report is filed)."""
    from apps.machines.models import MachineSession
    from apps.machines.sessions_state import effective_member_id, sessions_on
    if not sessions_on(space):
        raise errors.not_eligible()
    session = (MachineSession.objects.select_related("machine").prefetch_related("amendments")
               .filter(makerspace=space, pk=session_id).first())
    if session is None or member is None or effective_member_id(session) != member.pk:
        raise errors.not_eligible()
    return session, "machine", session.machine
