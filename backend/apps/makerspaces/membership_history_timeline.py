"""The membership history timeline in words (X28), built from the term history.

Behind `membership.history`. Each entry is `{at, kind, text, plan, until, reason}`:
`at`/`until` stay ISO instants so the client prints them in the reader's own locale,
and `text` is the plain sentence. Staff-written reasons (an extension's "why") are shown
to staff only; the member sees that it happened, not the internal note.
"""
from apps.makerspaces.models import MembershipTermStatusEvent
from apps.makerspaces.models_membership_rules import TermKind, TermStanding

_OPENED = {TermKind.NEW: "Joined on the {plan} plan", TermKind.RENEWAL: "Renewed on the {plan} plan",
           TermKind.REINSTATEMENT: "Came back on the {plan} plan"}
_TEXT = {
    TermStanding.UPCOMING: "A {plan} term was booked to start later",
    TermStanding.GRACE: "The {plan} term ended; renewal grace began",
    TermStanding.ENDED: "The {plan} term ended and the next one followed",
    TermStanding.LAPSED: "The membership lapsed",
    TermStanding.CANCELLED: "The {plan} term was cancelled",
    TermStanding.EXTENDED: "The {plan} term was extended",
}


def _entry(event, *, for_staff):
    term = event.term
    plan = term.plan.name
    if event.status == TermStanding.ACTIVE:
        text = _OPENED.get(term.kind, _OPENED[TermKind.NEW]).format(plan=plan)
    else:
        text = _TEXT.get(event.status, "{plan}: " + event.status).format(plan=plan)
    lifetime = term.is_lifetime
    return {"at": event.effective_at, "kind": event.status, "text": text, "plan": plan,
            "until": None if lifetime else event.ends_at, "lifetime": lifetime,
            "reason": event.reason if for_staff else ""}


def timeline(membership, *, for_staff=False, limit=200):
    events = (MembershipTermStatusEvent.objects.filter(membership=membership)
              .select_related("term__plan").order_by("-effective_at", "-pk")[:limit])
    entries = [_entry(event, for_staff=for_staff) for event in events]
    if membership.revoked_at and membership.status == "revoked":
        entries.append({"at": membership.revoked_at, "kind": "ended", "text": "The membership ended",
                        "plan": "", "until": None, "lifetime": False,
                        "reason": membership.revocation_reason if for_staff else ""})
    return sorted(entries, key=lambda row: row["at"], reverse=True)
