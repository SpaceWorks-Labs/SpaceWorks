"""Decision 248: the community exports -- roster, guest passes, volunteer hours, minors consent, staff roster.

All are per space, for `manage_members` (the staff roster for the Space Manager's `manage_makerspace`), and
identity-bearing: they name people, so they are unschedulable, never organization totals, and a superadmin reads
them only inside an open PII window. Scoped PII rules: the minors export carries the minor's name and a whole-year
age, the guardian's NAME and the consent state only -- never a birth date, guardian email or phone, the typed
signature or the consent text.
"""

from django.db.models import Sum

from apps.makerspaces.models import (
    GuestPass, MakerspaceMembership, MinorProfile, VolunteerHourEntry,
)
from apps.operations.report_types import ReportResult
from apps.operations.reports_membership_l4_lists import _latest_terms, _standing

ROSTER_FIELDS = ("member_number", "name", "email", "status", "access_status", "plan", "standing", "verified",
                 "minor", "volunteer_minutes", "joined_at")
GUEST_PASS_FIELDS = ("pass_id", "kind", "status", "holder", "sponsor", "valid_from", "valid_until", "waiver_version",
                     "converted")
VOLUNTEER_FIELDS = ("member", "entries", "approved_minutes", "pending_minutes", "last_worked_on")
MINOR_FIELDS = ("minor", "age", "guardian_name", "consent_state", "consent_terms_version", "consent_valid_until")
STAFF_FIELDS = ("name", "email", "roles", "status", "receives_notifications", "since")


def _cap(rows, limit):
    return rows if limit is None else rows[:limit]


def _name(user):
    return (user.display_name or user.get_full_name() or user.username) if user else ""


def build_roster_export(makerspace_id, *, limit=None, date_range=None, now=None, actor=None):
    from django.utils import timezone
    from apps.makerspaces.membership_number import formatted, pattern_for
    from apps.makerspaces.models import Makerspace
    space, now = Makerspace.objects.get(pk=makerspace_id), now or timezone.now()
    latest, pattern = _latest_terms(space), pattern_for(space)
    minors = set(MinorProfile.objects.filter(makerspace=space, cleared_at__isnull=True).values_list("user_id", flat=True))
    hours = dict(VolunteerHourEntry.objects.filter(makerspace=space, status="approved").values_list("member_id").annotate(
        total=Sum("minutes")))
    rows = []
    members = MakerspaceMembership.objects.filter(makerspace=space, user__account_kind="member").select_related("user")
    for member in members.order_by("member_number", "pk"):
        term = latest.get(member.pk)
        rows.append({"member_number": formatted(member.member_number, pattern, member.created_at.year),
                     "name": _name(member.user), "email": member.user.email, "status": member.status,
                     "access_status": member.user.access_status, "plan": term.plan.name if term else "",
                     "standing": _standing(term, now), "verified": member.verified_at is not None,
                     "minor": member.user_id in minors, "volunteer_minutes": hours.get(member.user_id, 0),
                     "joined_at": member.created_at})
    return ReportResult(ROSTER_FIELDS, _cap(rows, limit), {
        "definition": "Every community member of the space with status, plan standing, verification, minor flag "
                      "and approved volunteer minutes."})


def build_guest_passes_export(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.operations.reports_common import apply_range
    passes = apply_range(GuestPass.objects.filter(makerspace_id=makerspace_id), "valid_from", date_range)
    rows = [{"pass_id": p.pk, "kind": p.kind, "status": p.status, "holder": _name(p.holder),
             "sponsor": _name(p.sponsor), "valid_from": p.valid_from, "valid_until": p.valid_until,
             "waiver_version": p.waiver_version or "", "converted": p.converted_membership_id is not None}
            for p in passes.select_related("holder", "sponsor").order_by("-valid_from", "-pk")]
    return ReportResult(GUEST_PASS_FIELDS, _cap(rows, limit), {
        "definition": "Guest passes issued in the period, with holder, sponsor, validity and whether the guest later joined."})


def build_volunteer_hours_export(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.operations.reports_common import apply_range
    days = None if date_range is None else tuple(None if value is None else value.date() for value in date_range)
    entries = apply_range(VolunteerHourEntry.objects.filter(makerspace_id=makerspace_id), "worked_on", days)
    people = {}
    for entry in entries.select_related("member").order_by("worked_on", "pk"):
        row = people.setdefault(entry.member_id, {"member": _name(entry.member), "entries": 0, "approved_minutes": 0,
                                                  "pending_minutes": 0, "last_worked_on": None})
        row["entries"] += 1
        if entry.status == "approved":
            row["approved_minutes"] += entry.minutes
        elif entry.status == "pending":
            row["pending_minutes"] += entry.minutes
        row["last_worked_on"] = entry.worked_on
    rows = sorted(people.values(), key=lambda r: (-r["approved_minutes"], r["member"]))
    return ReportResult(VOLUNTEER_FIELDS, _cap(rows, limit), {
        "definition": "Volunteer hours per person: approved minutes, minutes still waiting for approval, last day worked."})


def build_minors_consent_export(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.makerspaces.minors import age_of, current_consent
    rows = []
    profiles = MinorProfile.objects.filter(makerspace_id=makerspace_id, cleared_at__isnull=True).select_related(
        "user", "makerspace").order_by("pk")
    for profile in profiles:
        consent = current_consent(profile)
        rows.append({"minor": _name(profile.user), "age": age_of(profile), "guardian_name": profile.guardian_name,
                     "consent_state": "valid" if consent else "none",
                     "consent_terms_version": consent.terms_version if consent else "",
                     "consent_valid_until": consent.valid_until if consent else None})
    return ReportResult(MINOR_FIELDS, _cap(rows, limit), {
        "definition": "Minors on record with the current guardian-consent state. No birth date, guardian contact, "
                      "signature or consent text is exported."})


def build_staff_roster_export(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.accounts.rbac_roles import additional_roles_prefetch
    staff = (MakerspaceMembership.staff_tracks.filter(makerspace_id=makerspace_id).select_related("user", "assigned_role")
             .prefetch_related(additional_roles_prefetch()).order_by("user__username", "pk"))
    rows = []
    for member in staff:
        names = [member.assigned_role.name] if member.assigned_role_id else []
        names += [extra.role.name for extra in member.additional_roles.all()]
        rows.append({"name": _name(member.user), "email": member.user.email, "roles": ", ".join(names),
                     "status": member.status, "receives_notifications": member.receives_notifications,
                     "since": member.created_at})
    return ReportResult(STAFF_FIELDS, _cap(rows, limit), {
        "definition": "Everyone holding staff roles in the space with their roles and status."})
