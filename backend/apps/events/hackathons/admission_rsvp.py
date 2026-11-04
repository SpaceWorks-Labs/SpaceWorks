"""Atomic individual/cohort RSVP; offers cannot overrun hard registration seats."""
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .admission_errors import check_version, fail
from .admission_models import HackathonApplication, HackathonApplicationCohort
from .admission_transactions import command, notice, record
from .admission_workflow import transition_registration_locked
from .capacity_admission import require_hard_room


def subject_applications_locked(app):
    if app.cohort_id:
        cohort = HackathonApplicationCohort.objects.select_for_update().get(pk=app.cohort_id, event_id=app.event_id)
        return cohort, list(HackathonApplication.objects.select_for_update().filter(cohort=cohort).order_by("pk"))
    return None, [app]


def end_group_locked(ctx, applications, state, *, reason_code):
    for app in applications:
        if app.state not in ("submitted", "offered", "waitlisted", "confirmed"):
            fail("invalid_transition", "This application can no longer change.")
        transition_registration_locked(application_id=app.pk, registration_id=app.registration_id,
            transition="waitlist" if state == "waitlisted" else "cancel", actor=ctx.actor,
            reason_code=reason_code, locks=ctx.locks)
        old = app.state
        app.state, app.response_at, app.rsvp_accepted_at = state, timezone.now(), None
        app.version += 1
        if state == "waitlisted":
            app.queue_position_at = timezone.now()
        app.save()
        record(ctx, "application_" + state, app, old_state=old, new_state=state, reason_code=reason_code)
        notice(ctx, app, "application_" + state)
        from .team_lifecycle import eligibility_changed_locked
        eligibility_changed_locked(ctx, app)


def rsvp(*, event_id, actor, data, application_id=None):
    staff = application_id is not None
    with command(event_id=event_id, actor=actor, data=data,
                 action=f"application.staff_rsvp:{application_id}" if staff else "application.rsvp",
                 permission="review_applications", owner=not staff) as ctx:
        rows = HackathonApplication.objects.filter(event=ctx.event)
        app = get_object_or_404(rows, pk=application_id) if staff else get_object_or_404(rows, member=actor)
        if ctx.reference:
            return app
        # Cohort parent precedes every application child lock.
        cohort, applications = subject_applications_locked(app)
        if not cohort:
            app = HackathonApplication.objects.select_for_update().get(pk=app.pk)
            applications = [app]
        else:
            app = next(a for a in applications if a.pk == app.pk)
        check_version(app, data["expected_version"])
        if app.state != "offered" or any(a.state != "offered" for a in applications):
            fail("invalid_transition", "This offer cannot be answered.")
        if data["decision"] == "accept" and any(a.date_review_required for a in applications):
            fail("event_date_changed", "Review your answers for the event start date.")
        now = timezone.now()
        if any(not a.rsvp_due_at or now >= a.rsvp_due_at for a in applications):
            fail("offer_expired", "The RSVP deadline has passed.")
        decision = data["decision"]
        reason = data.get("reason_code", "participant_rsvp")
        if decision != "accept":
            state = "declined" if decision == "decline" else "waitlisted"
            end_group_locked(ctx, applications, state, reason_code=reason)
            if cohort:
                cohort.state, cohort.version = state, cohort.version + 1
                cohort.save()
        else:
            from apps.events.staged_forms.admission_hooks import require_action_locked
            require_action_locked(event=ctx.event, member_id=app.member_id, action="rsvp")
            app.rsvp_accepted_at, app.response_at = now, now
            app.version += 1
            app.save()
            record(ctx, "rsvp_accepted", app, on_behalf=staff, reason_code=reason)
            if all(a.rsvp_accepted_at for a in applications):
                require_hard_room(ctx.event, applications)
                for item in applications:
                    transition_registration_locked(application_id=item.pk, registration_id=item.registration_id,
                        transition="confirm", actor=actor, reason_code=reason, locks=ctx.locks)
                    item.state = "confirmed"
                    if item.pk != app.pk:
                        item.version += 1
                    item.save()
                    record(ctx, "application_confirmed", item, version=item.version)
                    notice(ctx, item, "application_confirmed")
                if cohort:
                    cohort.state, cohort.version = "confirmed", cohort.version + 1
                    cohort.save()
                from .admission_feature import applications_only
                if ctx.config.team_mode == "solo" and not applications_only(ctx.event.makerspace):
                    from .team_workflow import create_solo_locked
                    create_solo_locked(ctx, app)
        if decision != "accept":
            from .admission_promotion import promote_locked
            promote_locked(ctx, exclude_application_ids=tuple(a.pk for a in applications))
        ctx.finish("application", app.pk)
        return app


def withdraw(*, event_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action="application.withdraw", owner=True) as ctx:
        app = get_object_or_404(HackathonApplication, event=ctx.event, member=actor)
        if ctx.reference:
            return app
        cohort, applications = subject_applications_locked(app)
        if not cohort:
            app = HackathonApplication.objects.select_for_update().get(pk=app.pk)
            applications = [app]
        else:
            app = next(a for a in applications if a.pk == app.pk)
        check_version(app, data["expected_version"])
        from apps.events.models import EventRegistration
        if EventRegistration.objects.filter(pk__in=[a.registration_id for a in applications], status="attended").exists():
            fail("invalid_transition", "An attended application cannot be withdrawn.")
        end_group_locked(ctx, applications, "withdrawn", reason_code=data["reason_code"])
        if cohort:
            cohort.state, cohort.version = "withdrawn", cohort.version + 1
            cohort.save()
        from .admission_promotion import promote_locked
        promote_locked(ctx, exclude_application_ids=tuple(a.pk for a in applications))
        ctx.finish("application", app.pk)
        return app


def extend_rsvp(*, event_id, application_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"application.extend_rsvp:{application_id}",
                 permission="review_applications") as ctx:
        app = get_object_or_404(HackathonApplication, event=ctx.event, pk=application_id)
        if ctx.reference:
            return app
        cohort, applications = subject_applications_locked(app)
        if not cohort:
            app = HackathonApplication.objects.select_for_update().get(pk=app.pk)
            applications = [app]
        else:
            app = next(a for a in applications if a.pk == app.pk)
        check_version(app, data["expected_version"])
        deadline = data["rsvp_due_at"]
        if deadline <= timezone.now() or deadline > min(ctx.event.ends_at, timezone.now() + timedelta(days=30)):
            fail("invalid_deadline", "Use a future RSVP deadline within the event and 30 days.", status=400)
        if any(a.state != "offered" for a in applications):
            fail("invalid_transition", "Only an open offer may be extended.")
        for item in applications:
            item.rsvp_due_at, item.version = deadline, item.version + 1
            item.save()
            record(ctx, "rsvp_extended", item, reason_code=data["reason_code"], version=item.version)
            notice(ctx, item, "rsvp_extended")
        ctx.finish("application", app.pk)
        return app
