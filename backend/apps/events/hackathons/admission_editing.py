"""Before-lock answer edits preserve frozen admission selections and money."""
from django.utils.translation import gettext
from .admission_errors import fail
from .admission_transactions import record
from .admission_ports import ports


def require_unchanged_admission(application, selection):
    registration = application.registration
    values = selection.values
    if "invite_code" in values or "promo_code" in values:
        fail("admission_locked", gettext("Codes cannot be redeemed after submission."))
    expected = {"ticket_type_id": registration.ticket_type_id, "email": registration.email, "phone": registration.phone}
    if any(key in values and values[key] != value for key, value in expected.items()):
        fail("admission_locked", gettext("Submitted ticket, quote and contacts cannot be changed."))


def persist_answer_edit_locked(ctx, application, prepared, data):
    if "coc" in data:
        coc = data["coc"]
        if coc.get("accepted") is not True:
            fail("coc_required", gettext("Accept the code of conduct."), status=400)
        if coc["revision"] != ctx.config.coc_revision:
            fail("coc_revision_changed", gettext("Review the current code of conduct."))
        from django.utils import timezone
        application.coc_revision, application.coc_accepted_at = coc["revision"], timezone.now()
        application.save(update_fields=["coc_revision", "coc_accepted_at"])
    if "optional_consents" in data:
        from django.utils import timezone
        requested = data["optional_consents"]
        if requested.get("mlh_data_sharing") and not ctx.config.optional_mlh_schema:
            fail("optional_consent_unavailable", gettext("This event does not request MLH sharing."), status=400)
        if "mlh_data_sharing" in requested:
            application.optional_consents = {**application.optional_consents, "mlh_data_sharing": {
                "accepted": requested["mlh_data_sharing"],
                "version": ctx.config.optional_mlh_schema.get("revision", 1), "at": timezone.now().isoformat()}}
            application.save(update_fields=["optional_consents"])
            record(ctx, "application_optional_consent_changed", application,
                   purpose="mlh_data_sharing", accepted=requested["mlh_data_sharing"])
    ports().registration.mirror_answers_locked(application_id=application.pk,
        registration_id=application.registration_id, prepared=prepared, locks=ctx.locks)
    record(ctx, "application_answers_edited", application, version=application.version)
