"""Member-card issuance report (X27): counts only, no person appears.

Active cards, members without a card, and -- over the period -- cards issued (by hand and
automatically), reissued, revoked and emailed, public card checks (the daily aggregate)
and open "photo needs update" requests.
"""
from django.utils import timezone

from apps.operations.report_types import ReportResult

FIELDS = ("metric", "value")


def build_card_issuance(makerspace_id, *, limit=None, date_range=None, now=None, actor=None, grain=None):
    from apps.audit.models import AuditLog
    from apps.card_designs.models import CardPhotoRequest, CardVerifyCheckDay
    from apps.makerspaces.models import MakerspaceMembership, MemberCard
    now = now or timezone.now()
    start, end = date_range or (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), now)
    cards = MemberCard.objects.filter(makerspace_id=makerspace_id)
    active = cards.filter(revoked_at__isnull=True, membership__isnull=False)
    carded = active.values_list("membership_id", flat=True)
    members = MakerspaceMembership.objects.filter(makerspace_id=makerspace_id, status="active",
                                                  member_number__isnull=False)
    logs = AuditLog.objects.filter(makerspace_id=makerspace_id, created_at__gte=start, created_at__lt=end)

    def count(action):
        return logs.filter(action=action).count()

    checks = CardVerifyCheckDay.objects.filter(makerspace_id=makerspace_id, day__gte=start.date(), day__lte=end.date())
    rows = [
        {"metric": "active_cards", "value": active.count()},
        {"metric": "members_without_card", "value": members.exclude(pk__in=carded).count()},
        {"metric": "issued", "value": count("member_card.issued")},
        {"metric": "auto_issued", "value": count("member_card.auto_issued")},
        {"metric": "reissued", "value": count("member_card.reissued")},
        {"metric": "revoked", "value": count("member_card.revoked")},
        {"metric": "emailed", "value": count("member_card.emailed")},
        {"metric": "public_checks", "value": sum(row.count for row in checks)},
        {"metric": "open_photo_requests", "value": CardPhotoRequest.objects.filter(
            makerspace_id=makerspace_id, member_card__isnull=False, resolved_at__isnull=True).count()},
    ]
    return ReportResult(FIELDS, rows if limit is None else rows[:limit], {
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "definition": "Member cards in counts: nothing here names a person."})
