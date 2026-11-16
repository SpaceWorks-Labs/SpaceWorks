"""Which event an L6 charge belongs to, for the per-event finance views (#100).

A series-pass order names no single event; its money stays domain `events` with no
event id, like a ledger receipt that names none.
"""


def subject_event_ids(subjects):
    """`{(subject_type, subject_id): event_id}` for `event_order` and `event_venue_fee` subjects."""
    from .models import EventOrder, EventVenueFee

    wanted = {"event_order": set(), "event_venue_fee": set(), "submission_fee": set(), "team_registration": set(),
              "event_deposit": set()}
    for subject_type, subject_id in subjects:
        if subject_type in wanted:
            wanted[subject_type].add(subject_id)
    found = {}
    if wanted["event_order"]:
        for pk, event_id in EventOrder.objects.filter(pk__in=wanted["event_order"]).values_list("pk", "event_id"):
            found[("event_order", pk)] = event_id
    if wanted["event_venue_fee"]:
        for pk, event_id in EventVenueFee.objects.filter(pk__in=wanted["event_venue_fee"]).values_list(
                "pk", "event_id"):
            found[("event_venue_fee", pk)] = event_id
    # Lane L21b: entry fees and team charges name their event through the project or team.
    from .models import HackathonSubmission, HackathonTeam
    for subject_type, model in (("submission_fee", HackathonSubmission), ("team_registration", HackathonTeam)):
        if wanted[subject_type]:
            for pk, event_id in model.objects.filter(pk__in=wanted[subject_type]).values_list("pk", "event_id"):
                found[(subject_type, pk)] = event_id
    # Hack-money G10: a deposit names its event through the registration.
    if wanted["event_deposit"]:
        from .models import EventRegistration
        for pk, event_id in EventRegistration.objects.filter(pk__in=wanted["event_deposit"]).values_list(
                "pk", "event_id"):
            found[("event_deposit", pk)] = event_id
    return found
