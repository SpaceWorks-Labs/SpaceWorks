"""Only writer of application state; registration changes use the G bridge."""
from django.utils.translation import gettext
import json
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from .admission_errors import check_version, fail
from .admission_inputs import typed_admission_input, effective_contacts
from .admission_models import HackathonApplication
from .admission_ports import ports
from .admission_transactions import assert_locked, command, notice, record


def require_application_open(event, config, now):
    if (event.status != "published" or now >= event.ends_at
            or (config.application_opens_at and now < config.application_opens_at)
            or (config.application_closes_at and now >= config.application_closes_at)):
        fail("applications_closed", gettext("Applications are closed."))


def save_application(*, event, actor, payload, submit=False):
    data, selection = typed_admission_input(payload, draft=not submit)
    from apps.events import inline_forms
    inline = inline_forms.split_inline(data)
    if inline and not submit:
        fail("inline_forms_submit_only", gettext("Answer event forms when submitting."), status=400)
    from .admission_transactions import member_event
    event, config = member_event(actor, event.pk, event.makerspace_id)
    existing = HackathonApplication.objects.filter(event=event, member=actor).first()
    repair_fields = {"operation_id", "expected_version", "host_waiver_id", "host_waiver_version", "host_waiver_accepted"}
    if submit and existing and existing.state != "draft" and set(payload) <= repair_fields:
        from .admission_repair import repair_host_consent
        return repair_host_consent(event_id=event.pk, actor=actor, data=data), 200
    subject = AnswerSubject(event_id=event.pk, owner_member_id=actor.pk, kind=SubjectKind.APPLICATION,
        **({"subject_id": existing.pk} if existing else {"creation_operation_id": data["operation_id"]}))
    # No KMS, account-row lock or first-use key provisioning may run below this line.
    from django.apps import apps
    has_receipt = apps.get_model("events", "EventCommandReceipt").objects.filter(
        event=event, actor=actor, operation_uuid=data["operation_id"]).exists()
    editable = existing is None or existing.state in ("draft", "submitted", "rejected", "declined", "expired", "withdrawn")
    prepared = None if has_receipt or not editable else ports().forms.prepare(event=event, config=config, actor=actor,
                                     subject=subject, payload=data, draft=not submit and (existing is None or existing.state != "submitted"))
    if prepared is not None and prepared.subject != subject:
        raise RuntimeError("Prepared answers have the wrong owner/subject.")
    # The outer digest covers the complete inline payload; preparation follows the replay check.
    prepared_inline = inline_forms.prepare(event=event, actor=actor, operation_id=data["operation_id"],
        inline=inline, base_forms=inline_forms.base_save_forms(prepared.derivations)) if prepared is not None else inline_forms.EMPTY
    with command(event_id=event.pk, actor=actor, data=data, owner=True,
                 action="application.submit" if submit else "application.edit",
                 normalized_body={**prepared.normalized_input, **inline} if prepared is not None else None) as ctx:
        actor = ctx.actor
        if ctx.reference:
            return get_object_or_404(HackathonApplication, pk=ctx.reference["id"], event=ctx.event, member=actor), ctx.reference["status"]
        application = HackathonApplication.objects.select_for_update().filter(event=ctx.event, member=actor).first()
        check_version(application, data["expected_version"])
        answer_edit = bool(application and application.state == "submitted" and not application.answer_locked_at)
        if inline and answer_edit:
            fail("inline_forms_submit_only", gettext("Answer event forms when first submitting."), status=400)
        inline_result = {}
        if application and application.state != "draft":
            from .admission_editing import require_unchanged_admission
            require_unchanged_admission(application, selection)
        if prepared is None:
            fail("programme_dependency_unavailable", gettext("Retry this command to prepare its current inputs."), status=503)
        reopening = bool(application and application.state in ("rejected", "declined", "expired", "withdrawn") and not submit)
        if application and application.state != "draft" and not reopening and not answer_edit:
            fail("invalid_transition", gettext("This application is no longer editable."))
        now = timezone.now()
        require_application_open(ctx.event, ctx.config, now)
        if data.get("event_date_revision") != ctx.event.event_date_revision:
            fail("event_date_changed", gettext("The event date changed. Review your answers."))
        ports().forms.require_current_locked(event=ctx.event, config=ctx.config, prepared=prepared, locks=ctx.locks)
        if "ticket_type_id" in selection.values:
            from apps.events.ticketing import select_ticket
            select_ticket(ctx.event, selection.values["ticket_type_id"], actor)
        if reopening:
            from .admission_answers import archive_locked
            archive_locked(ctx, application)
            transition_registration_locked(application_id=application.pk, registration_id=application.registration_id,
                transition="reopen", actor=actor, reason_code="participant_reapply", locks=ctx.locks)
            previous = application.state
            application.state, application.cohort = "draft", None
            application.coc_revision = application.coc_accepted_at = application.answer_locked_at = None
            application.offered_at = application.rsvp_due_at = application.rsvp_accepted_at = None
            application.optional_consents = {}
            record(ctx, "application_reopened", application, old_state=previous, new_state="draft")
        if submit:
            from apps.events.ticketing import ticket_selection_required
            if ticket_selection_required(ctx.event) and "ticket_type_id" not in selection.values:
                fail("ticket_selection_required", gettext("Choose an available ticket type."), status=400,
                     fields={"ticket_type_id": ["Required."]})
            coc = data.get("coc") or {}
            if coc.get("accepted") is not True:
                fail("coc_required", gettext("Accept the code of conduct."), status=400, fields={"coc": ["Required."]})
            if coc.get("revision") != ctx.config.coc_revision:
                fail("coc_revision_changed", gettext("The code of conduct changed. Review it again."), fields={"coc": [str(ctx.config.coc_revision)]})
            if data.get("optional_consents", {}).get("mlh_data_sharing") and not ctx.config.optional_mlh_schema:
                fail("optional_consent_unavailable", gettext("This event does not request MLH sharing."), status=400)
            contacts = effective_contacts(actor, selection)
        created = application is None
        application = application or HackathonApplication(event=ctx.event, member=actor)
        # F's canonical snapshot contains derivation references, never stored age.
        application.answers_changed_at = now
        application.answer_event_date_revision = ctx.event.event_date_revision
        from zoneinfo import ZoneInfo
        application.answer_as_of_date = ctx.event.starts_at.astimezone(ZoneInfo(ctx.event.timezone_name)).date()
        application.date_review_required = False
        application.answers_snapshot = json.dumps(prepared.snapshot, separators=(",", ":"))
        application.form_schema_version = prepared.snapshot.get("version", 1)
        application.form_revision = prepared.snapshot.get("form_revision", 1)
        draft_selection = json.loads(application.admission_draft)
        draft_selection.update(selection.draft_values())
        application.admission_draft = json.dumps(draft_selection)
        if not created:
            application.version += 1
        application.save()
        if not submit and not answer_edit and prepared.saved_intent is not None:
            raise RuntimeError("Drafts cannot enqueue saved-detail intents.")
        attached = ports().forms.attach_locked(application=application, prepared=prepared, locks=ctx.locks, store_intent=submit or answer_edit)
        if attached is not None:
            prepared = attached
            application.answers_snapshot = json.dumps(prepared.snapshot, separators=(",", ":"))
            application.save(update_fields=["answers_snapshot"])
        if answer_edit:
            from .admission_editing import persist_answer_edit_locked
            persist_answer_edit_locked(ctx, application, prepared, data)
        elif submit:
            registration_id = ports().registration.create_pending_locked(event=ctx.event, member=actor,
                selection=selection, contacts=contacts, prepared=prepared, subject=subject, locks=ctx.locks)
            from apps.events.models import EventRegistration
            registration = EventRegistration.objects.filter(pk=registration_id, event=ctx.event, member=actor).first()
            if registration is None or registration.status != "pending_approval" or registration.custom_answers != prepared.snapshot:
                raise RuntimeError("Registration bridge did not preserve the pending application snapshot.")
            application.registration_id = registration_id
            application.state, application.submitted_at = "submitted", now
            application.coc_revision, application.coc_accepted_at = ctx.config.coc_revision, now
            application.optional_consents = {"mlh_data_sharing": {
                "accepted": data.get("optional_consents", {}).get("mlh_data_sharing", False),
                "version": ctx.config.optional_mlh_schema.get("revision", 1), "at": now.isoformat()}}
            application.save()
            inline_result = inline_forms.bind_locked(event=ctx.event, actor=actor, registration=registration,
                application=application, prepared=prepared_inline, locks=ctx.locks)
            record(ctx, "application_submitted", application, version=application.version)
            notice(ctx, application, "application_submitted")
            if ctx.config.review_mode == "auto" and ctx.config.team_mode != "team_together":
                from .admission_decisions import auto_release_locked
                auto_release_locked(ctx, application)
                application.refresh_from_db()
        elif not answer_edit:
            if application.registration_id:
                ports().registration.mirror_answers_locked(application_id=application.pk,
                    registration_id=application.registration_id, prepared=prepared, locks=ctx.locks)
            record(ctx, "application_saved", application, version=application.version)
        status = 201 if created else 200
        ctx.finish("application", application.pk, status=status, **({"inline": inline_result} if inline_result else {}))
        return application, status


def transition_registration_locked(*, application_id, registration_id, transition, locks,
                                   actor=None, reason_code="admission"):
    assert_locked(locks, locks.event_id)
    app = get_object_or_404(HackathonApplication, pk=application_id, event_id=locks.event_id)
    if registration_id != app.registration_id or not registration_id:
        fail("not_found", gettext("Not found."), status=404)
    return ports().registration.transition_locked(application_id=app.pk, registration_id=registration_id,
        transition=transition, actor=actor, reason_code=reason_code, locks=locks)


def require_team_eligible(*, team_id, event_id, at):
    from .team_models import HackathonTeam
    team = get_object_or_404(HackathonTeam, pk=team_id, event_id=event_id)
    from .admission_transactions import require_programme
    config = require_programme(team.event)
    members = list(team.memberships.filter(state="active").select_related("application__registration", "member"))
    from .admission_cohorts import roster_hash
    exceptions = team.eligibility_exceptions.filter(roster_hash=roster_hash(members), valid_until__gt=at)
    size_allowed = config.team_min <= len(members) <= config.team_max or (bool(members) and exceptions.filter(rule="team_size").exists())
    if team.state == "disbanded" or team.eligibility_issue or not size_allowed:
        fail("team_ineligible", gettext("The team needs a complete eligible roster."))
    from apps.events.registration_access import require_registration_access
    for membership in members:
        require_registration_access(team.event, membership.member)
        app = membership.application
        if app.event_id != event_id or app.member_id != membership.member_id or app.state != "confirmed" or not app.registration_id:
            fail("team_ineligible", gettext("Every team member must confirm their place."))
        if app.registration.status not in ("registered", "attended"):
            fail("team_ineligible", gettext("A team registration is no longer active."))
        if config.attendance_required and app.registration.status != "attended" and not exceptions.filter(rule="attendance", member_id=membership.member_id).exists():
            fail("attendance_required", gettext("Every team member must check in before submitting."))
    if config.team_mode == "team_together":
        from .admission_cohorts import require_sealed_roster
        require_sealed_roster(team, members)
