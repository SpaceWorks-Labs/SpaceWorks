"""Certificate merge values: what each kind is called and what the {{tags}} print.

Issuance freezes the kind/award/role/place labels into ``layout_snapshot["merge"]`` so a
retried render reproduces the same bytes even if a prize is renamed later. Certificates
issued before the snapshot existed fall back to labels derived from their immutable kind.
"""

from zoneinfo import ZoneInfo

KIND_LABELS = {
    "attendance": "Attendance", "participant": "Participant", "finalist": "Finalist",
    "winner": "Winner", "volunteer_thanks": "Volunteer", "mentor_thanks": "Mentor",
    "judge_thanks": "Judge", "organiser_thanks": "Organiser",
}
# The document title, the notification wording and the member area all name the real kind.
KIND_TITLES = {
    "attendance": "Certificate of attendance", "participant": "Certificate of participation",
    "finalist": "Finalist certificate", "winner": "Winner's certificate",
    "volunteer_thanks": "Certificate of thanks for volunteering",
    "mentor_thanks": "Certificate of thanks for mentoring",
    "judge_thanks": "Certificate of thanks for judging",
    "organiser_thanks": "Certificate of thanks for organising",
}
KIND_NOUNS = {
    "attendance": "attendance certificate", "participant": "participation certificate",
    "finalist": "finalist certificate", "winner": "winner's certificate",
    "volunteer_thanks": "volunteer thank-you certificate", "mentor_thanks": "mentor thank-you certificate",
    "judge_thanks": "judge thank-you certificate", "organiser_thanks": "organiser thank-you certificate",
}
ROLE_LABELS = {"co_organizer": "Organiser", "volunteer": "Volunteer", "mentor": "Mentor",
               "judge": "Judge", "sponsor_rep": "Sponsor representative"}
SAMPLE = {
    "attendance": ("Attendee", ""), "participant": ("Participant", ""),
    "finalist": ("Participant", "Finalist · Best hardware hack"),
    "winner": ("Participant", "1st place · Best hardware hack"),
    "volunteer_thanks": ("Volunteer", ""), "mentor_thanks": ("Mentor", ""),
    "judge_thanks": ("Judge", ""), "organiser_thanks": ("Organiser", ""),
}


def ordinal(number):
    """1st, 2nd, 3rd, 4th … 11th, 12th, 13th … 21st, 22nd, 101st, 111th."""
    number = int(number)
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def kind_label(kind):
    return KIND_LABELS.get(kind, "Attendance")


def kind_title(kind):
    return KIND_TITLES.get(kind, KIND_TITLES["attendance"])


def kind_noun(kind):
    return KIND_NOUNS.get(kind, KIND_NOUNS["attendance"])


def _registration_role(kind):
    return "Participant" if kind in ("participant", "finalist", "winner") else "Attendee"


def _place(*, event_id, member_id, award_id, result_revision_id):
    """The member's rank for this prize in this exact result, or None."""
    if not award_id or not result_revision_id:
        return None
    from apps.events.judging.models_results import EventAward
    from apps.events.judging.ports import runtime
    for award in EventAward.objects.filter(prize_id=award_id, result_id=result_revision_id,
                                           result__event_id=event_id).order_by("rank", "pk"):
        snapshot = runtime().snapshot(award.submission_snapshot_id)
        if snapshot.event_id == event_id and member_id in snapshot.member_ids:
            return award.rank
    return None


def issuance_merge(*, event_id, kind, member_id, subject_kind, subject_id, award_id=None,
                   result_revision_id=None):
    """Frozen labels for one certificate. Called once, inside the issuance transaction."""
    if subject_kind == "role_assignment":
        from apps.events.contributions.models_roles import EventRoleAssignment
        role_key = EventRoleAssignment.objects.filter(pk=subject_id, event_id=event_id).values_list(
            "role", flat=True).first()
        role = ROLE_LABELS.get(role_key, kind_label(kind))
    else:
        role = _registration_role(kind)
    prize = ""
    if award_id:
        from apps.events.judging.models_definitions import HackathonPrize
        prize = HackathonPrize.objects.filter(pk=award_id, event_id=event_id).values_list(
            "name", flat=True).first() or ""
    rank = _place(event_id=event_id, member_id=member_id, award_id=award_id,
                  result_revision_id=result_revision_id) if kind in ("winner", "finalist") else None
    place = f"{ordinal(rank)} place" if rank else ""
    if place and prize:
        award = f"{place} · {prize}"
    elif kind == "finalist":
        award = f"Finalist · {prize}" if prize else "Finalist"
    else:
        award = prize
    return {"kind": kind_label(kind), "award": award, "role": role, "place": place}


def sample_merge(kind):
    role, award = SAMPLE.get(kind or "attendance", SAMPLE["attendance"])
    place = "1st place" if (kind or "") == "winner" else ""
    return {"kind": kind_label(kind or "attendance"), "award": award, "role": role, "place": place}


def frozen_merge(certificate):
    snapshot = getattr(certificate, "layout_snapshot", None) or {}
    merge = snapshot.get("merge")
    if isinstance(merge, dict):
        return merge
    kind = getattr(certificate, "kind", None) or "attendance"
    award = ""
    if getattr(certificate, "award_id", None):
        award = getattr(certificate.award, "name", "") or ""
    role = kind_label(kind) if kind.endswith("_thanks") else _registration_role(kind)
    return {"kind": kind_label(kind), "award": award, "role": role, "place": ""}


def merge_values(certificate):
    zone = ZoneInfo(getattr(certificate, "event_timezone_name", "UTC") or "UTC")
    merge = frozen_merge(certificate)
    return {"name": certificate.recipient_name, "event": certificate.event_title,
            "eventDate": certificate.event_starts_at.astimezone(zone).strftime("%d %B %Y"),
            "organisation": certificate.issuer_name,
            "issueDate": certificate.issued_at.strftime("%d %B %Y"),
            "certificate_id": str(certificate.serial),
            "kind": merge.get("kind", ""), "award": merge.get("award", ""),
            "role": merge.get("role", ""), "place": merge.get("place", ""),
            # crewRole predates {{role}} and now carries the same real event role. Rows issued
            # before the frozen labels existed keep printing "" so their bytes reproduce.
            "crewRole": merge.get("role", "") if _frozen(certificate) else ""}


def _frozen(certificate):
    return isinstance((getattr(certificate, "layout_snapshot", None) or {}).get("merge"), dict)


def document_title(certificate):
    """PDF title. Rows issued before frozen labels keep their original title bytes."""
    if not _frozen(certificate):
        return f"Attendance certificate {certificate.serial}"
    return f"{kind_title(getattr(certificate, 'kind', 'attendance'))} {certificate.serial}"
