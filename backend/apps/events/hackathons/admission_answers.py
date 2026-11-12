"""Application answer locks/revisions; P owns encrypted derivation source history."""
from django.utils.translation import gettext
from zoneinfo import ZoneInfo
from django.db.models import Max
from django.utils import timezone
from .admission_errors import fail
from .admission_models import HackathonApplicationAnswerRevision
from .admission_ports import ports
from .admission_transactions import record


def lock_answers_locked(ctx, application, *, at=None, closing=False):
    if application.answer_locked_at:
        return
    application.answer_event_date_revision = ctx.event.event_date_revision
    application.answer_as_of_date = ctx.event.starts_at.astimezone(ZoneInfo(ctx.event.timezone_name)).date()
    application.answer_locked_at = at or timezone.now()
    kwargs = {"closing": True} if closing else {}
    ports().forms.lock_answers_locked(application=application, at=application.answer_locked_at, locks=ctx.locks, **kwargs)
    application.save(update_fields=["answer_event_date_revision", "answer_as_of_date", "answer_locked_at"])
    record(ctx, "application_answers_locked", application, version=application.version,
           event_date_revision=application.answer_event_date_revision)


def require_date_reviewed(application):
    if application.date_review_required:
        fail("event_date_changed", gettext("Review your answers for the event start date."))


def archive_locked(ctx, application):
    if not application.answer_locked_at:
        return None
    sequence = (application.answer_revisions.aggregate(value=Max("sequence"))["value"] or 0) + 1
    revision = HackathonApplicationAnswerRevision.objects.create(application=application, sequence=sequence,
        answers_snapshot=application.answers_snapshot, profile_snapshot=application.profile_snapshot,
        form_schema_version=application.form_schema_version, form_revision=application.form_revision,
        coc_revision=application.coc_revision, coc_accepted_at=application.coc_accepted_at,
        answer_event_date_revision=application.answer_event_date_revision, answer_as_of_date=application.answer_as_of_date,
        locked_at=application.answer_locked_at)
    ports().forms.archive_answers_locked(application=application, revision_id=revision.pk, locks=ctx.locks)
    record(ctx, "application_answers_archived", revision, application_id=application.pk, sequence=sequence)
    return revision
