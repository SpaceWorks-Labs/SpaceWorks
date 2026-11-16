"""The one answer to "which registrations does this member hold in this space".

Shared by the profile counts, the profile's recent-attended list, member activity and the
check-in QR lookup, so those four cannot drift apart. It lives in the events app rather than
in `makerspaces` so it disappears with an events tombstone.

Three rules, each of which had a wrong alternative:

- **Provenance, not current collaboration.** An accepted collaboration authorizes discovery
  and creation; `registered_via_makerspace` records where the participation actually
  happened. Filtering on the live collaboration instead would let an administrator editing a
  collaborator list retroactively delete a member's history and silently break the QR of
  someone already holding a ticket.
- **But not past the host's own lifecycle.** Durable history survives a collaborator being
  removed; it must NOT survive the host being archived or withdrawing its events module,
  since the event itself is then not something the host exposes at all.
- **Never match on email.** `EventRegistration.member` is nullable, so an email-only public
  registration correctly never appears here. A shared household address is enough for an
  email match to attach one person's attendance to another person's published profile.
"""


def registrations_for_space(makerspace, user, *, include_disabled_hosts=False):
    """This member's registrations made via `makerspace`, while its host still exposes them.

    Cancellation may include disabled hosts only to explicitly check their module gate
    and return 400. Ordinary history and QR reads keep hiding those registrations.
    """
    from django.db.models import Q

    from apps.events.models import EventRegistration
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import servable_queryset

    registrations = servable_queryset(EventRegistration.objects.filter(
        # A NULL provenance falls back to the host, which is what every row meant before
        # provenance existed. This read fails OPEN to the previous behaviour on purpose: the
        # column is SET_NULL and can also be absent on a row written outside `register()`
        # (a superadmin in `/control/`, a data import), and a member's own history quietly
        # disappearing is a worse failure than showing a row whose routing is unknown. It
        # also means the backfill migration is a tidiness measure rather than load-bearing.
        Q(registered_via_makerspace=makerspace)
        | Q(registered_via_makerspace__isnull=True, event__makerspace=makerspace),
        member=user,
    ), relation="event__makerspace")
    if include_disabled_hosts:
        return registrations
    # `module_enabled` needs the row, so the host set is resolved in Python. It is bounded by
    # the number of distinct hosts this member registered through -- one, for everybody who
    # never attended a joint event -- not by the number of registrations.
    host_ids = set(registrations.values_list("event__makerspace_id", flat=True))
    if not host_ids:
        return registrations.none()
    enabled = [
        host.pk
        for host in Makerspace.objects.filter(pk__in=host_ids)
        if module_enabled(host, "events")
    ]
    return registrations.filter(event__makerspace_id__in=enabled)


HISTORY_LIMIT = 50


def _history_event(event):
    return {"id": event.pk, "title": event.title, "starts_at": event.starts_at, "ends_at": event.ends_at,
            "location": event.location, "status": event.status}


def history_for_space(makerspace, user):
    """Registrations, attendance and speaking for one person in one space (newest first).

    Shared by the member's own event history and the staff member drawer so the two can
    never disagree. Registrations reuse `registrations_for_space` (provenance, host
    lifecycle, never email); speaking reuses `speaker_history.contributions_for`.
    """
    from django.db.models import Count, Q

    from apps.events.models import EventRegistration
    from apps.events.speaker_history import contributions_for

    registrations = registrations_for_space(makerspace, user).select_related("event")
    counts = registrations.aggregate(
        registered=Count("pk", filter=Q(status__in=(EventRegistration.Status.REGISTERED,
                                                    EventRegistration.Status.ATTENDED))),
        attended=Count("pk", filter=Q(status=EventRegistration.Status.ATTENDED)),
        cancelled=Count("pk", filter=Q(status=EventRegistration.Status.CANCELLED)),
    )
    speaking = list(contributions_for(user, makerspace))
    return {
        "counts": {**{key: value or 0 for key, value in counts.items()}, "speaking": len(speaking)},
        "registrations": [
            {"registration_id": row.pk, "status": row.status, "event": _history_event(row.event)}
            for row in registrations.order_by("-event__starts_at", "-pk")[:HISTORY_LIMIT]
        ],
        "speaking": [
            {"speaker_id": row.speaker_id, "role": row.role, "occurred_at": row.occurred_at,
             "event": _history_event(row.event)}
            for row in speaking[:HISTORY_LIMIT]
        ],
    }
