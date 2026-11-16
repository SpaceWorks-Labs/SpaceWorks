"""Copy configuration only; people, permission issuers and work never travel."""

from apps.audit.services import record
from apps.events import event_authority
from apps.events.programme_locks import assert_lock_context
from apps.makerspaces.resource_clone import bounded_children, copy_fields

from .models_roles import EventRolePosting, EventSponsor, EventSponsorTrack
from .models_shifts import EventShift

POSTING_FIELDS = (
    "role", "title", "description", "briefing", "skills", "visibility", "approval_required",
    "opens_at", "closes_at", "requirements", "form_schema",
)
SHIFT_FIELDS = (
    "starts_at", "ends_at", "zone", "task", "capacity", "signup_deadline", "waitlist_enabled",
    "approval_required", "requirements", "grace_minutes",
)


def copy_definitions_locked(*, source, target, actor, locks):
    assert_lock_context(locks)
    if locks.event_id != target.pk or source.makerspace_id != target.makerspace_id:
        raise ValueError("Clone definitions require same-tenant source and target locks.")
    event_authority.require(actor, source, "edit_details")
    event_authority.require_tenant(actor, target.makerspace)
    sponsors = {}
    for row in bounded_children(EventSponsor.objects.filter(event=source).order_by("pk")):
        # References into the source page are not identities in the copied page.
        sponsors[row.pk] = EventSponsor.objects.create(event=target, makerspace=target.makerspace,
            organization_id=row.organization_id, label=row.label, active=row.active)
    postings = {}
    for row in bounded_children(EventRolePosting.objects.filter(event=source).order_by("pk")):
        postings[row.pk] = EventRolePosting.objects.create(event=target, makerspace=target.makerspace,
            state="draft", permission_preset=[], permission_issuer=None, **copy_fields(row, POSTING_FIELDS))
    for row in bounded_children(EventShift.objects.filter(event=source, kind="volunteer").order_by("pk")):
        EventShift.objects.create(event=target, makerspace=target.makerspace, posting=postings[row.posting_id],
            kind="volunteer", state="closed", permission_preset=[], **copy_fields(row, SHIFT_FIELDS))
    from apps.events.mentoring.models_queue import EventHelpType
    from apps.events.mentoring.models_rounds import MentorRound
    for row in bounded_children(EventHelpType.objects.filter(event=source).order_by("pk")):
        EventHelpType.objects.create(event=target, makerspace=target.makerspace, **copy_fields(row, (
            "key", "label", "skill_tags", "priority", "open_limit", "organizer_contact_action",
            "claim_minutes", "expiry_minutes")))
    for row in bounded_children(MentorRound.objects.filter(event=source, practice_run_id=None).order_by("pk")):
        MentorRound.objects.create(event=target, makerspace=target.makerspace, state="draft", **copy_fields(row, (
            "index", "key", "label", "opens_at", "closes_at", "form_schema_version", "form_schema",
            "note_keys", "rating_keys", "help_trigger_rules", "allow_fresh_eyes_override", "allow_conflict_override")))
    record(actor, "event.programme.contribution_definitions_copied", makerspace=target.makerspace,
           target=target, meta={"source_event_id": source.pk, "postings": len(postings), "sponsors": len(sponsors)})
    return {key: value.pk for key, value in sponsors.items()}


def copy_sponsor_tracks_locked(*, source, target, sponsors, tracks):
    for row in bounded_children(EventSponsorTrack.objects.filter(event=source).order_by("pk")):
        EventSponsorTrack.objects.create(event=target, makerspace=target.makerspace,
            sponsor_id=sponsors[row.sponsor_id], track_id=tracks[row.track_id])
