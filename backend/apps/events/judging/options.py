"""L21b per-event hackathon options: email switches (C-37), fees, and the one-time results email.

New events have no row, so every switch is off and no fee is charged. Existing events got a row with
today's emails on when the table was added (migration), so nothing they did changes.
"""

from django.http import Http404

from apps.audit.services import record
from .boundary import command, mutation, notice
from .errors import ProgrammeError
from .models_options import HackathonProgrammeOptions
from .models_results import JudgingNotice, ResultPublicationState
from .serializers import validated
from .serializers_l21b import OptionsInput

FIELDS = ("results_email", "submission_receipt_email", "finalists_email", "refund_on_disqualification",
          "refund_on_withdrawal", "refund_if_not_shortlisted", "entry_fee", "team_fee")


def options_for(event_id):
    return HackathonProgrammeOptions.objects.filter(event_id=event_id).first()


def option(event, key):
    row = options_for(getattr(event, "pk", event))
    return getattr(row, key) if row is not None else HackathonProgrammeOptions._meta.get_field(key).default


def currency(makerspace):
    from apps.payments.models import MakerspacePaymentSettings
    return MakerspacePaymentSettings.for_makerspace(makerspace).default_currency


def _current_result(event):
    state = ResultPublicationState.objects.filter(event=event).select_related("current_announcement__result").first()
    return state.current_announcement.result if state and state.current_announcement_id else None


def results_email_sent(event):
    result = _current_result(event)
    return bool(result) and JudgingNotice.objects.filter(event=event, kind="results_published",
                                                         source_id=result.pk, revision=result.version).exists()


def projection(event):
    row = options_for(event.pk)
    values = {key: getattr(row, key) if row else HackathonProgrammeOptions._meta.get_field(key).default for key in FIELDS}
    return {"id": row.pk if row else 0, "event_id": event.pk, "version": row.version if row else 0,
            "allowed_actions": ["edit", "send_results_email"], "currency": currency(event.makerspace),
            "results_email_sent": results_email_sent(event),
            "published_result_version": getattr(_current_result(event), "version", None), **values}


def read(event_id, *, actor):
    from apps.events import event_authority
    from .ports import runtime
    event = event_authority.get_event(actor, event_id, "manage_hackathon")
    runtime().require_programme(event)
    return projection(event)


def update(event_id, *, actor, data):
    values = validated(OptionsInput, data, partial=True)
    with mutation(event_id, actor) as (event, _):
        def run():
            row = HackathonProgrammeOptions.objects.select_for_update().filter(event=event).first()
            if (row.version if row else 0) != values["expected_version"]:
                raise ProgrammeError("stale_version", "This item changed.", current_version=row.version if row else 0)
            if row is None:
                row = HackathonProgrammeOptions(event=event, version=0)
            changes = {key: values[key] for key in FIELDS if key in values and values[key] != getattr(row, key)}
            from .feature import ENTRY_FEES, PAID_TEAMS, enabled
            for key, feature in (("entry_fee", ENTRY_FEES), ("team_fee", PAID_TEAMS)):
                if changes.get(key) and not enabled(event.makerspace, feature):
                    raise ProgrammeError("feature_disabled", "Switch this fee on for the space first.", status=403)
            for key, value in changes.items():
                setattr(row, key, value)
            row.version += 1
            row.save()
            record(actor, "event.programme_options.updated", makerspace=event.makerspace, target=row,
                   meta={"event_id": event.pk, "fields": sorted(changes)})
            return projection(event)
        return command(event, actor, values, path="programme-options", run=run)


def send_results_email(event_id, *, actor, data):
    """One time per announced result: create the results notice even when the switch is off."""
    from .serializers import CommandInput
    values = validated(CommandInput, data)
    with mutation(event_id, actor, permission=None) as (event, _):
        def run():
            result = _current_result(event)
            if result is None:
                raise Http404
            if values["expected_version"] != result.version:
                raise ProgrammeError("stale_version", "This item changed.", current_version=result.version)
            if results_email_sent(event):
                raise ProgrammeError("already_sent", "The results email was already sent for these results.")
            notice(event, "results_published", result.pk, result.version)
            record(actor, "event.results_email.sent", makerspace=event.makerspace, target=result,
                   meta={"event_id": event.pk, "version": result.version})
            return projection(event)
        return command(event, actor, values, path="results/send-email", run=run)
