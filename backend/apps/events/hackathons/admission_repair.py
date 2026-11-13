"""Consent-only owner retry never changes admission, quote, answers or state."""
from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from apps.events.host_waivers import require_host_waiver, stamp_host_waiver, HostWaiverRequired
from apps.events.models import EventRegistration
from .admission_errors import check_version, fail, ProgrammeError
from .admission_models import HackathonApplication
from .admission_transactions import command, record


def repair_host_consent(*, event_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action="application.repair_consent", owner=True) as ctx:
        app = get_object_or_404(HackathonApplication.objects.select_for_update(), event=ctx.event, member=actor)
        if ctx.reference:
            return app
        check_version(app, data["expected_version"])
        registration = get_object_or_404(EventRegistration.objects.select_for_update(), pk=app.registration_id,
                                         event=ctx.event, member=actor)
        if app.state not in ("submitted", "offered", "waitlisted", "confirmed") or registration.status not in ("pending_approval", "waitlisted", "registered"):
            fail("invalid_transition", gettext("This registration cannot renew consent."))
        if ctx.event.registration_audience != "participating_organizations":
            fail("invalid_transition", gettext("Host consent repair does not apply to this event."))
        try:
            waiver = require_host_waiver(ctx.event, actor, actor=actor, registration=registration,
                **{k: data.get(k) for k in ("host_waiver_id", "host_waiver_version", "host_waiver_accepted")})
        except HostWaiverRequired as exc:
            error = ProgrammeError("host_waiver_required", gettext("Review and accept the current host waiver."), status=400,
                fields={"host_waiver_accepted": ["Accept the current host waiver."]})
            error.detail["refresh_context_url"] = f"/api/v1/public/event-programmes/{ctx.event.public_token}/context/"
            raise error from exc
        stamp_host_waiver(registration, waiver, actor=actor, via=ctx.event.makerspace, event=ctx.event)
        app.version += 1
        app.save(update_fields=["version"])
        record(ctx, "host_consent_repaired", app, version=app.version)
        ctx.finish("application", app.pk)
        return app
