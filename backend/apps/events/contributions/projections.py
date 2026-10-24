from django.utils import timezone
from .api_common import envelope
from .models_roles import EventRoleAssignment
from .models_shifts import EventShiftSignup, EventShiftAttendance, EventContributionHours
from .ports import ports
from .subjects import subject_for


def role(row, *, detail=False, owner=False, actor=None):
    actions = ["withdraw"] if owner and row.state in ("draft", "proposed", "applied", "approved") else []
    if owner and row.state in ("draft", "proposed", "applied") and row.answer_locked_at is None:
        actions.extend(["edit", "submit"])
    if owner and row.state == "proposed":
        actions.append("decline")
    data = {**envelope(row, actions), "role": row.role, "posting_id": row.posting_id,
        "submitted_at": row.submitted_at, "decision": row.state if row.state in (
            "approved", "declined", "revoked", "completed") else None, "grant": None, "save_intent": None,
        "entitlement_active": row.state == "approved" and not row.imported_inert}
    if not owner:
        data["imported_inert"] = row.imported_inert
    if detail:
        options = {"actor_id": actor.pk} if actor else {}
        data.update(ports().forms.project(subject=subject_for(row), audience="owner" if owner else "organizer", **options))
    return data


def posting(row, *, actor=None, detail=False, public=False):
    data = {**envelope(row), "role": row.role, "title": row.title, "description": row.description}
    if detail and actor:
        data.update(ports().forms.context(actor_id=actor.pk, event_id=row.event_id, schema=row.form_schema))
        own = EventRoleAssignment.objects.filter(posting=row, member=actor,
            state__in=["draft", "applied", "approved"]).first()
        data["application"] = role(own, owner=True) if own else None
        data["host_waiver"] = posting_waiver(row, actor=actor, own=own)
    return data


def posting_waiver(row, *, actor, own=None):
    if not (row.requirements.get("host_waiver_required")
            or row.event.registration_audience == "participating_organizations"):
        return None
    from apps.makerspaces.models import MakerspaceWaiver, MakerspaceMembership
    from apps.events.host_waivers import has_current_host_consent
    waiver = MakerspaceWaiver.objects.filter(makerspace_id=row.makerspace_id, is_active=True).first()
    if waiver is None:
        return None
    membership = MakerspaceMembership.objects.filter(makerspace_id=row.makerspace_id,
        user=actor, status="active").first()
    return {"id": waiver.pk, "version": waiver.version, "body": waiver.body,
        "acceptance_required": not has_current_host_consent(waiver, membership, own)}


def signup(row, *, owner=True):
    attendance = EventShiftAttendance.objects.filter(signup=row).first()
    hours = EventContributionHours.objects.filter(signup=row, state__in=["verified", "adjusted"]).first()
    actions = []
    if owner and row.state in ("applied", "waitlisted", "approved"):
        actions.append("withdraw")
    if attendance and row.state == "approved":
        if attendance.state == "scheduled":
            actions.append("check-in")
        if attendance.state == "checked_in":
            actions.append("check-out")
    data = {**envelope(row, actions), "shift_id": row.shift_id,
        "attendance": attendance.state if attendance else None,
        "verified_minutes": hours.minutes if hours else None}
    if not owner:
        data.update(member_id=row.member_id, assignment_id=row.assignment_id)
    return data


def shift(row, *, actor=None):
    booked = row.bookings.filter(state="booked").count() if row.kind == "office_hours" else row.signups.filter(state="approved").count()
    own = EventShiftSignup.objects.filter(shift=row, member=actor).first() if actor else None
    return {**envelope(row), "posting_id": row.posting_id, "kind": row.kind,
        "starts_at": row.starts_at, "ends_at": row.ends_at, "task": row.task, "zone": row.zone,
        "capacity": row.capacity, "available": None if row.capacity == 0 else max(0, row.capacity - booked),
        "signup": signup(own) if own else None, "mentor_card": None}


def admin_shift(row, actor):
    items = []
    for item in row.signups.order_by("queue_at", "pk"):
        data = signup(item, owner=False)
        if item.state in ("applied", "waitlisted"):
            data["allowed_actions"].extend(["approve", "withdraw"])
        if item.state == "approved" and data["attendance"] == "checked_out" and item.member_id != actor.pk:
            data["allowed_actions"].append("verify-hours" if data["verified_minutes"] is None else "adjust-hours")
        items.append(data)
    return {**shift(row), "signups": items, **{key: getattr(row, key) for key in (
        "signup_deadline", "mentor_assignment_id", "grace_minutes", "waitlist_enabled", "approval_required",
        "requirements", "permission_preset")}}


def admin_posting(row):
    return {**posting(row), **{key: getattr(row, key) for key in (
        "briefing", "skills", "visibility", "approval_required", "opens_at", "closes_at",
        "requirements", "permission_preset", "form_schema")}}
