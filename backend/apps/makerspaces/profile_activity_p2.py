"""Additional counts-only sources; the frozen engine owns consent/module gates."""

from django.db.models import Q
from django.utils import timezone

from .profile_activity_sources import ActivityMilestone, ActivitySource, register_activity_source


def speaking(profile, start, end):
    from .profile_history_speaking import speaking_contributions

    for contribution in speaking_contributions(profile):
        if start <= contribution.occurred_at < end:
            # Multiple session links/scans for one event on one day are one contribution.
            yield ActivityMilestone(f"events.Event:{contribution.event.pk}", contribution.occurred_at)


def loans(profile, start, end):
    from apps.hardware_requests.models import HardwareRequest, PublicToolLoan, ReturnEvent

    owner = {"makerspace_id": profile.membership.makerspace_id,
             "requester_id": profile.membership.user_id}
    issued_states = ["issued", "partially_returned", "returned", "closed_with_issue"]
    # Direct/self-checkout loans have a backing request. Count the physical loan once,
    # using PublicToolLoan's identity rather than counting both representations.
    reviewed = HardwareRequest.objects.filter(**owner, status__in=issued_states,
                                             public_tool_loan__isnull=True)
    for pk, moment in reviewed.filter(issued_at__gte=start, issued_at__lt=end).values_list("pk", "issued_at"):
        yield ActivityMilestone(f"hardware_requests.HardwareRequest:{pk}", moment)
    for pk, moment in ReturnEvent.objects.filter(
        makerspace_id=profile.membership.makerspace_id, request_id__in=reviewed.values("pk"),
        created_at__gte=start, created_at__lt=end,
    ).values_list("request_id", "created_at"):
        yield ActivityMilestone(f"hardware_requests.HardwareRequest:{pk}", moment)
    direct = PublicToolLoan.objects.filter(
        **owner, request__requester_id=profile.membership.user_id,
        request__makerspace_id=profile.membership.makerspace_id,
        request__status__in=issued_states, status__in=["checked_out", "returned"],
    ).filter(Q(checked_out_at__gte=start, checked_out_at__lt=end)
             | Q(status="returned", returned_at__gte=start, returned_at__lt=end))
    for row in direct.only("pk", "status", "checked_out_at", "returned_at"):
        yield ActivityMilestone(f"hardware_requests.PublicToolLoan:{row.pk}", row.checked_out_at)
        if row.status == "returned" and row.returned_at is not None:
            yield ActivityMilestone(f"hardware_requests.PublicToolLoan:{row.pk}", row.returned_at)


def bookings(profile, start, end):
    from apps.bookings.models import Booking

    now = timezone.now()
    rows = Booking.objects.filter(
        space__makerspace_id=profile.membership.makerspace_id,
        member_id=profile.membership.user_id, status__in=["confirmed", "completed"],
    ).filter(Q(arrived_at__gte=start, arrived_at__lt=end, arrived_at__lte=now)
             | Q(status="completed", ends_at__gte=start, ends_at__lt=end, ends_at__lte=now))
    for row in rows.only("pk", "status", "arrived_at", "ends_at"):
        if row.arrived_at is not None and row.arrived_at <= now:
            yield ActivityMilestone(f"bookings.Booking:{row.pk}", row.arrived_at)
        if row.status == "completed" and row.ends_at <= now:
            yield ActivityMilestone(f"bookings.Booking:{row.pk}", row.ends_at)


def register_sources():
    register_activity_source(ActivitySource("speaking", "events", speaking))
    register_activity_source(ActivitySource("loans", "request_workflow", loans))
    register_activity_source(ActivitySource("bookings", "bookings", bookings))
