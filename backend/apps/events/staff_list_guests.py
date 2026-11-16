"""The guest list's extra filters, columns and counted presets (parity E-B5: C16, D22, B25).

* `reply` filters by the "are you still coming?" answer (`yes`, `no`, `waiting`, `not_asked`).
* `list` + `collected` (`yes` / `no`) narrow the guests to those who did or did not collect on one custom
  check-in list; only undone-free scans count.
* Each live check-in list adds a `Check-in: <name>` column holding the time of the guest's first collection
  (blank when none). The columns appear only while `events.checkin_lists` is on.
* `presets` are the ready-made filters with server-side counts; a saved view may store any of them.
"""
from django.db.models import Count, Q
from django.utils.translation import gettext

from apps.makerspaces.platform import feature_enabled

from .models_checkin_lists import EventCheckInList, EventCheckInListScan
from .models_registration import EventRegistration

REPLIES = {"yes": Q(attendance_reply__answer="yes"), "no": Q(attendance_reply__answer="no"),
           "waiting": Q(attendance_reply__isnull=False, attendance_reply__answer=""),
           "not_asked": Q(attendance_reply__isnull=True)}


def _lists_on(event):
    return feature_enabled(event.makerspace, "events.checkin_lists")


def filter_rows(event, rows, params):
    reply = params.get("reply")
    if reply:
        if reply not in REPLIES:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"reply": gettext("Use yes, no, waiting or not_asked.")})
        rows = rows.filter(REPLIES[reply])
    list_id, collected = params.get("list"), params.get("collected")
    if list_id and collected in ("yes", "no") and _lists_on(event) and str(list_id).isdigit():
        done = EventCheckInListScan.objects.filter(checkin_list_id=int(list_id), checkin_list__event=event,
                                                   undone_at__isnull=True).values("registration_id")
        rows = rows.filter(pk__in=done) if collected == "yes" else rows.exclude(pk__in=done)
    return rows.select_related("attendance_reply")


def list_columns(event):
    """`Check-in: <name>` per live list, disambiguated when two lists share a name."""
    if not _lists_on(event):
        return ()
    lists = EventCheckInList.objects.filter(event=event, archived_at__isnull=True).order_by("position", "pk")
    names, columns = {}, []
    for row in lists:
        names[row.name] = names.get(row.name, 0) + 1
    for row in lists:
        label = f"Check-in: {row.name}" + (f" (#{row.pk})" if names[row.name] > 1 else "")
        columns.append((row.pk, label))
    return tuple(columns)


def annotate(event, chunk, extra):
    """Add the reply and per-list collection time to each projected row of one keyset chunk."""
    times = {}
    if extra:
        scans = EventCheckInListScan.objects.filter(
            checkin_list__event=event, undone_at__isnull=True, registration_id__in=[r.pk for r in chunk],
        ).order_by("pk").values_list("registration_id", "checkin_list_id", "scanned_at")
        for registration_id, list_id, at in scans:
            times.setdefault((registration_id, list_id), at)
    for row in chunk:
        reply = getattr(row, "attendance_reply", None)
        extras = {label: times.get((row.pk, list_id), "") for list_id, label in extra}
        yield row, (reply.answer or "waiting") if reply is not None else "", extras


def presets(event):
    """Ready-made guest filters with their counts, in one aggregate query."""
    status = EventRegistration.Status
    spec = [("all", gettext("Everyone"), {}, Q()),
            ("confirmed", gettext("Confirmed"), {"status": status.REGISTERED}, Q(status=status.REGISTERED)),
            ("attended", gettext("Checked in"), {"status": status.ATTENDED}, Q(status=status.ATTENDED)),
            ("waitlisted", gettext("Waitlisted"), {"status": status.WAITLISTED}, Q(status=status.WAITLISTED)),
            ("pending", gettext("Awaiting approval"), {"status": status.PENDING_APPROVAL},
             Q(status=status.PENDING_APPROVAL))]
    if feature_enabled(event.makerspace, "events.attendance_confirmation"):
        spec += [("waiting_reply", gettext("Not replied yet"), {"reply": "waiting"}, REPLIES["waiting"]),
                 ("not_coming", gettext("Said they are not coming"), {"reply": "no"}, REPLIES["no"])]
    counts = EventRegistration.objects.filter(event=event).aggregate(
        **{key: Count("pk", filter=condition, distinct=True) for key, _label, _filters, condition in spec})
    return [{"key": key, "label": label, "filters": {k: str(v) for k, v in filters.items()}, "count": counts[key]}
            for key, label, filters, _condition in spec]
