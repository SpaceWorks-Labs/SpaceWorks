"""Who would receive which certificate (C10): candidates from attendance, published results and
roles, each checked by the same eligibility service issuance uses, with skip reasons. Nothing is
written; staff confirm the returned subjects through the existing batch command."""
from django.utils.translation import gettext
from django.http import Http404
from rest_framework.exceptions import APIException, NotFound, ValidationError

from apps.events.credentials.boundary import event_command
from apps.events.models_certificates import EventAttendanceCertificate
from .merge import KIND_TITLES, issuance_merge
from .preparation import prepare_issuance
from .subjects import require_subject

GROUPS = ("attendance", "participants", "awards", "roles")
ROLE_KINDS = {"volunteer": "volunteer_thanks", "mentor": "mentor_thanks", "judge": "judge_thanks",
              "co_organizer": "organiser_thanks"}
LIMIT = 2000


def _registrations(event_id, member_ids):
    from apps.events.models_registration import EventRegistration
    rows = EventRegistration.objects.filter(event_id=event_id, member_id__in=member_ids,
                                            status__in=("registered", "attended")).order_by("pk")
    return {row.member_id: row.pk for row in rows}


def candidates(event, groups):
    """Subjects to check, in a stable order. Awards follow the currently announced result."""
    from apps.events.models_registration import EventRegistration
    result = []
    if "attendance" in groups:
        result += [{"subject_kind": "registration", "subject_id": pk, "kind": "attendance"} for pk in
                   EventRegistration.objects.filter(event=event, status="attended", member__isnull=False)
                   .order_by("pk").values_list("pk", flat=True)[:LIMIT]]
    if "participants" in groups or "awards" in groups:
        from apps.events.judging.ports import runtime
        snapshots = [row for row in runtime().snapshots(event.pk) if row.current and row.eligible]
        if "participants" in groups:
            members = sorted({member for row in snapshots for member in row.member_ids})
            result += [{"subject_kind": "registration", "subject_id": pk, "kind": "participant"}
                       for pk in _registrations(event.pk, members).values()]
        if "awards" in groups:
            result += _awards(event)
    if "roles" in groups:
        from apps.events.contributions.models_roles import EventRoleAssignment
        for row in EventRoleAssignment.objects.filter(event=event, role__in=ROLE_KINDS, imported_inert=False,
                                                      state__in=("approved", "completed")).order_by("pk")[:LIMIT]:
            result.append({"subject_kind": "role_assignment", "subject_id": row.pk, "kind": ROLE_KINDS[row.role]})
    return result[:LIMIT]


def _awards(event):
    from apps.events.judging.models_results import EventAward, ResultPublicationState
    from apps.events.judging.ports import runtime
    state = ResultPublicationState.objects.filter(event=event).select_related("current_announcement").first()
    if state is None or state.current_announcement is None:
        return []
    result_id = state.current_announcement.result_id
    rows = []
    for award in EventAward.objects.filter(result_id=result_id).order_by("prize__order", "prize_id", "rank", "pk"):
        snapshot = runtime().snapshot(award.submission_snapshot_id)
        for member, registration in sorted(_registrations(event.pk, snapshot.member_ids).items()):
            rows.append({"subject_kind": "registration", "subject_id": registration,
                         "kind": "winner" if award.rank == 1 else "finalist",
                         "award_id": award.prize_id, "result_revision_id": result_id})
    return rows


def _live(item):
    field = "registration_id" if item["subject_kind"] == "registration" else "role_assignment_id"
    return EventAttendanceCertificate.objects.filter(**{field: item["subject_id"]}, kind=item["kind"],
                                                     award_id=item.get("award_id")).exclude(status="revoked").exists()


def _reason(exc):
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        detail = detail.get("detail") or next(iter(detail.values()), "")
    if isinstance(detail, list):
        detail = detail[0] if detail else ""
    return str(detail or "Not eligible.")


def plan(event, *, actor, groups):
    from apps.events import event_authority
    if not groups or set(groups) - set(GROUPS):
        raise ValidationError({"groups": gettext("Choose attendance, participants, awards or roles.")})
    event_authority.require(actor, event, None)
    subjects = candidates(event, groups)
    if not subjects:
        return {"event_version": event.version, "recipients": [], "skipped": [], "counts": {}}
    prepared = prepare_issuance(event.pk, subjects, for_issue=False)
    recipients, skipped = [], []
    with event_command(event.pk, actor=actor, account_ids=prepared.account_ids,
                       revalidate=prepared.revalidate) as (locked, _actor):
        for item in subjects:
            person = prepared.recipient(item["subject_kind"], item["subject_id"])
            row = {**item, "award_id": item.get("award_id"), "result_revision_id": item.get("result_revision_id"),
                   "name": person.name, "kind_title": KIND_TITLES[item["kind"]]}
            if _live(item):
                skipped.append({**row, "reason": "Already has this certificate."})
                continue
            try:
                subject = require_subject(locked, prepared=person, **{key: item.get(key) for key in (
                    "subject_kind", "subject_id", "kind", "award_id", "result_revision_id")})
            except (APIException, Http404) as exc:
                skipped.append({**row, "reason": _reason(exc)})
                continue
            row["award"] = issuance_merge(event_id=locked.pk, kind=item["kind"], member_id=subject.member_id,
                                          subject_kind=item["subject_kind"], subject_id=item["subject_id"],
                                          award_id=item.get("award_id"),
                                          result_revision_id=item.get("result_revision_id"))["award"]
            recipients.append(row)
        version = locked.version
    counts = {}
    for row in recipients:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    return {"event_version": version, "recipients": recipients, "skipped": skipped, "counts": counts}


def sample_context(event, *, actor, subject):
    """A not-stored render of one planned recipient with the design their kind would use."""
    from types import SimpleNamespace
    from django.utils import timezone
    from apps.events import event_authority
    from apps.events.certificate_templates import issuance_layout
    from .preparation import selected_template
    from .signatories import preview_signatures
    event_authority.require(actor, event, None)
    kind = subject["kind"]
    prepared = prepare_issuance(event.pk, [subject], for_issue=False)
    try:
        person = prepared.recipient(subject["subject_kind"], subject["subject_id"])
    except APIException as exc:
        raise NotFound() from exc
    snapshot = issuance_layout(selected_template(event, kind))
    snapshot["merge"] = issuance_merge(event_id=event.pk, kind=kind, member_id=person.member_id,
                                       subject_kind=subject["subject_kind"], subject_id=subject["subject_id"],
                                       award_id=subject.get("award_id"), result_revision_id=subject.get("result_revision_id"))
    preview_signatures(event, snapshot)
    return SimpleNamespace(layout_snapshot=snapshot, recipient_name=person.name, kind=kind, award_id=None,
                           event_title=event.title, issuer_name=event.makerspace.name,
                           event_timezone_name=event.timezone_name, event_starts_at=event.starts_at,
                           event_ends_at=event.ends_at, issued_at=timezone.now(), serial="PREVIEW", revision=0)
