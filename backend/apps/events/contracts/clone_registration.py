"""Programme definition clone composition. No applications or live pointers."""

from apps.audit.services import record
from apps.events.hackathons.admission_models import HackathonConfig, HackathonCocRevision
from apps.events.programme_locks import assert_lock_context
from apps.makerspaces.resource_clone import bounded_children, copy_fields

CONFIG_FIELDS = (
    "review_mode", "application_opens_at", "application_closes_at", "application_form",
    "team_mode", "finder_enabled", "team_min", "team_max", "team_lock_at", "team_eligibility",
    "review_count", "blind_review", "review_rubric", "rsvp_days", "offer_capacity",
    "submission_opens_at", "submission_deadline", "submission_grace_minutes", "late_policy",
    "attendance_required", "upload_policy", "upload_policy_version", "storage_budget_bytes",
    "coc_revision", "optional_mlh_schema",
)


def copy_programme_locked(*, source, target, actor, locks):
    assert_lock_context(locks)
    if locks.event_id != target.pk or target.makerspace_id != source.makerspace_id:
        raise ValueError("Clone scope changed.")
    config = HackathonConfig.objects.filter(event=source).first()
    if config:
        # Cloning never enables admission, restores a result or renews retention.
        HackathonConfig.objects.create(event=target, enabled=False, **copy_fields(config, CONFIG_FIELDS))
        for row in bounded_children(HackathonCocRevision.objects.filter(event=source).order_by("pk")):
            HackathonCocRevision.objects.create(event=target, revision=row.revision, body=row.body)
    from apps.events.contributions.clone import copy_definitions_locked, copy_sponsor_tracks_locked
    from apps.events.judging.clone import copy_definitions_locked as copy_judging
    sponsors = copy_definitions_locked(source=source, target=target, actor=actor, locks=locks)
    tracks = copy_judging(source_event_id=source.pk, target_event=target, actor=actor,
                          sponsor_map=sponsors, locks=locks)
    copy_sponsor_tracks_locked(source=source, target=target, sponsors=sponsors, tracks=tracks)
    record(actor, "event.programme.definitions_copied", makerspace=target.makerspace,
           target=target, meta={"source_event_id": source.pk})
