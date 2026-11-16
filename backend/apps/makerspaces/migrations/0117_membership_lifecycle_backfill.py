"""Back-fill the release-2 membership fields on existing rows (lane L4).

* member numbers: every membership holding the Member role, or holding any term, gets
  the next number in its space, in join order (created_at, pk), so numbering starts
  gapless at 1 (the same people `_activate_membership` and `create_term` number);
* membership source: read from the first `membership.joined` / `membership.approved`
  audit entry's `source` (approval, open, referral -> join; walk_in, staff_create ->
  manual); left blank when unknown;
* term kind and frozen currency/type: the first term of a membership is NEW, a term
  that follows its predecessor without a gap is a RENEWAL, one after a gap is a
  REINSTATEMENT. Prices are left null: what an old term was sold for was never stored;
* term history: the standing rows the term sweep and staff actions now write.

Reversing leaves the columns to the schema migration's reverse, which drops them.
"""
from datetime import timedelta

from django.db import migrations

JOIN_SOURCES = {"approval": "join", "open": "join", "referral": "join", "claim": "join", "invite": "join",
                "walk_in": "manual", "staff_create": "manual"}


def number_members(apps):
    Membership = apps.get_model("makerspaces", "MakerspaceMembership")
    Additional = apps.get_model("makerspaces", "MembershipAdditionalRole")
    member_ids = set(Membership.objects.filter(assigned_role__slug="member").values_list("pk", flat=True))
    member_ids |= set(Additional.objects.filter(role__slug="member").values_list("membership_id", flat=True))
    Term = apps.get_model("makerspaces", "MembershipTerm")
    member_ids |= set(Term.objects.values_list("membership_id", flat=True))
    counters, rows = {}, []
    # Member numbers are a community-track fact (unified accounts, makerspaces/0114): a staff
    # row carrying an additional "member" role is not a numbered member.
    for row in Membership.objects.filter(pk__in=member_ids, track="community").order_by(
            "makerspace_id", "created_at", "pk").only(
            "pk", "makerspace_id", "member_number"):
        counters[row.makerspace_id] = counters.get(row.makerspace_id, 0) + 1
        row.member_number = counters[row.makerspace_id]
        rows.append(row)
    Membership.objects.bulk_update(rows, ["member_number"], batch_size=500)


def record_sources(apps):
    Membership = apps.get_model("makerspaces", "MakerspaceMembership")
    AuditLog = apps.get_model("audit", "AuditLog")
    first = {}
    for target_id, meta in AuditLog.objects.filter(
        action__in=("membership.joined", "membership.approved"), target_type="makerspaces.makerspacemembership",
    ).order_by("created_at", "pk").values_list("target_id", "meta").iterator(chunk_size=2000):
        source = JOIN_SOURCES.get((meta or {}).get("source"))
        if source and str(target_id).isdigit():
            first.setdefault(int(target_id), source)
    rows = []
    for row in Membership.objects.filter(pk__in=list(first)).only("pk", "source"):
        row.source = first[row.pk]
        rows.append(row)
    Membership.objects.bulk_update(rows, ["source"], batch_size=500)


def classify_terms(apps):
    Term = apps.get_model("makerspaces", "MembershipTerm")
    previous, rows = {}, []
    for term in Term.objects.select_related("plan").order_by("membership_id", "starts_at", "pk").iterator(chunk_size=2000):
        before = previous.get(term.membership_id)
        if before is None:
            term.kind = "new"
        elif term.renewed_from_id or before.ends_at >= term.starts_at - timedelta(days=1):
            term.kind = "renewal"
        else:
            term.kind = "reinstatement"
        term.currency = term.plan.currency
        if term.status != "cancelled":
            previous[term.membership_id] = term
        rows.append(term)
    Term.objects.bulk_update(rows, ["kind", "currency"], batch_size=500)


def backfill_history(apps):
    """Seed the append-only standing history for terms opened before it existed: ACTIVE
    at the start, then ENDED (a successor starts within a day) or LAPSED at the end for
    an expired term, or CANCELLED when the cancellation was audited (else at its end)."""
    Term = apps.get_model("makerspaces", "MembershipTerm")
    Event = apps.get_model("makerspaces", "MembershipTermStatusEvent")
    AuditLog = apps.get_model("audit", "AuditLog")
    cancelled_at = dict(AuditLog.objects.filter(
        action="membership.term_cancelled", target_type="makerspaces.membershipterm",
    ).values_list("target_id", "created_at"))
    starts = {}
    for membership_id, starts_at in Term.objects.exclude(status="cancelled").values_list("membership_id", "starts_at"):
        starts.setdefault(membership_id, []).append(starts_at)
    rows = []
    for term in Term.objects.select_related("membership").order_by("pk").iterator(chunk_size=2000):
        base = {"makerspace_id": term.membership.makerspace_id, "membership_id": term.membership_id,
                "term_id": term.pk, "ends_at": term.ends_at}
        rows.append(Event(status="active", effective_at=term.starts_at, **base))
        if term.status == "cancelled":
            rows.append(Event(status="cancelled", effective_at=cancelled_at.get(str(term.pk), term.ends_at), **base))
        elif term.status == "expired":
            followed = any(term.ends_at - timedelta(days=1) <= other <= term.ends_at + timedelta(days=1)
                           for other in starts.get(term.membership_id, ()) if other != term.starts_at)
            rows.append(Event(status="ended" if followed else "lapsed", effective_at=term.ends_at, **base))
        if len(rows) >= 2000:
            Event.objects.bulk_create(rows)
            rows = []
    Event.objects.bulk_create(rows)


def forwards(apps, schema_editor):
    number_members(apps)
    record_sources(apps)
    classify_terms(apps)
    backfill_history(apps)


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0116_membership_lifecycle"),
        ("audit", "0009_audit_verification_runs"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
