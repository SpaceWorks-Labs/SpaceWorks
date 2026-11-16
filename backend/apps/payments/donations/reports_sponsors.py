"""Sponsor perks report (RP-3): each sponsor's checklist, due or fulfilled, finance-only.

A sponsor's name, tier and the perk text are the space's business data; the sponsor's
private contact (`contact_*`) and whoever ticked a perk off are never read into a row.
Tier template perks are not rows: only the copies on a sponsor are owed to anyone.
With a date range, a perk counts when it is due inside it, was fulfilled inside it, or has
no due date at all.
"""

from django.db.models import Q

from apps.makerspaces.local_time import local_now, to_local
from apps.operations.report_types import ReportResult

PERK_FIELDS = ("perk_id", "sponsor_id", "sponsor", "tier", "perk", "due_on", "state", "days_overdue",
               "fulfilled_on", "sponsor_archived")
STATES = ("overdue", "due", "open", "fulfilled")


def _state(perk, today):
    if perk.fulfilled_at is not None:
        return "fulfilled"
    if perk.due_on is None:
        return "open"
    return "overdue" if perk.due_on < today else "due"


def _in_range(queryset, space, date_range):
    if not date_range:
        return queryset
    start, end = date_range
    due, done = Q(), Q()
    if start is not None:
        due &= Q(due_on__gte=to_local(space, start).date())
        done &= Q(fulfilled_at__gte=start)
    if end is not None:
        due &= Q(due_on__lt=to_local(space, end).date())
        done &= Q(fulfilled_at__lt=end)
    return queryset.filter(Q(due_on__isnull=True) | due | (Q(fulfilled_at__isnull=False) & done))


def _perk_rows(space, date_range):
    from apps.payments.models import SponsorPerk

    today = local_now(space).date()
    perks = _in_range(SponsorPerk.objects.filter(makerspace=space, sponsor__isnull=False), space, date_range)
    perks = perks.select_related("sponsor", "sponsor__tier").only(
        "pk", "description", "due_on", "fulfilled_at", "sponsor", "sponsor__name", "sponsor__archived_at",
        "sponsor__tier", "sponsor__tier__name")
    rows = []
    for perk in perks:
        state = _state(perk, today)
        rows.append({
            "perk_id": perk.pk, "sponsor_id": perk.sponsor_id, "sponsor": perk.sponsor.name,
            "tier": perk.sponsor.tier.name if perk.sponsor.tier_id else "", "perk": perk.description,
            "due_on": perk.due_on, "state": state,
            "days_overdue": (today - perk.due_on).days if state == "overdue" else 0,
            "fulfilled_on": to_local(space, perk.fulfilled_at).date() if perk.fulfilled_at else None,
            "sponsor_archived": perk.sponsor.archived_at is not None,
        })
    rows.sort(key=lambda row: (STATES.index(row["state"]), row["due_on"] is None, row["due_on"] or today,
                               row["sponsor"].lower(), row["perk_id"]))
    return rows


def build_sponsor_perks(makerspace_id, *, limit=None, date_range=None, actor=None):
    from .reports import _spaces

    records = []
    for space in _spaces(makerspace_id):
        records.extend(_perk_rows(space, date_range))
    return ReportResult(PERK_FIELDS, records if limit is None else records[:limit], {
        "definition": "Every perk owed to a sponsor: overdue first, then due, then perks without a date, then "
                      "fulfilled ones.",
        "columns": "state: overdue (due date passed, not fulfilled), due (due date ahead), open (no due date), "
                   "fulfilled. days_overdue counts from the due date to today.",
        "privacy": "Sponsor contact details are never included.",
    })
