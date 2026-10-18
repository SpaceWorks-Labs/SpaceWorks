"""Owner date confirmation delegates encrypted derivation handling to P."""
from zoneinfo import ZoneInfo
from django.shortcuts import get_object_or_404
from .admission_errors import check_version, fail
from .admission_models import HackathonApplication
from .admission_ports import ports
from .admission_transactions import command, record


def review_date(*, event_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action="application.date_review", owner=True) as ctx:
        app = get_object_or_404(HackathonApplication.objects.select_for_update(), event=ctx.event, member=actor)
        if ctx.reference:
            return app
        check_version(app, data["expected_version"])
        as_of = app.answer_as_of_date if app.answer_locked_at else ctx.event.starts_at.astimezone(ZoneInfo(ctx.event.timezone_name)).date()
        revision = app.answer_event_date_revision if app.answer_locked_at else ctx.event.event_date_revision
        if data["confirmed"] is not True or data["event_date_revision"] != revision or data["as_of_date"] != as_of:
            fail("event_date_changed", "Review the current event date.")
        ports().forms.date_review_locked(application=app, revision=revision,
                                         as_of_date=as_of, locks=ctx.locks)
        app.date_review_required, app.version = False, app.version + 1
        app.save()
        record(ctx, "application_date_reviewed", app, version=app.version, event_date_revision=ctx.event.event_date_revision)
        ctx.finish("application", app.pk)
        return app
