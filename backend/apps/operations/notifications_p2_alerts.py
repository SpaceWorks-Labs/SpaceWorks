"""Operational alerts contain IDs and navigation, never mail bodies or destinations."""
from apps.accounts import rbac
from apps.integrations.models import EmailLog
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, fanout, identity, revision, safe_notification, scoped, staff_link
from apps.makerspaces.platform import module_enabled
from .models import StocktakeSession

STOCKTAKE = "operations.stocktake"
MAIL_FAILURE = "operations.email_failure"


def stocktake_revision(row, event):
    return revision(row.pk, row.completed_at if event == "completed" else row.started_at)


def stocktake_intent(row, event):
    return identity(row.makerspace_id, STOCKTAKE, row.pk, stocktake_revision(row, event), event)


def email_failure_intent(log):
    return identity(log.makerspace_id, MAIL_FAILURE, log.pk, revision(log.pk, "first_failure"), "email.failed")


def stocktake_eligible(envelope):
    row = scoped(StocktakeSession, envelope.makerspace_id).filter(pk=envelope.source_id).first()
    return bool(row and envelope.audience == "staff" and envelope.event in {"scheduled", "completed"}
        and module_enabled(envelope.makerspace, "stocktake")
        and row.status != "cancelled" and (envelope.event != "completed" or row.completed_at)
        and envelope.revision == stocktake_revision(row, envelope.event)
        and rbac.can(envelope.recipient, rbac.Action.EDIT_INVENTORY, envelope.makerspace_id))


def stocktake_body(row, event):
    return body(f"Stocktake {event}", f"Stocktake #{row.pk} is {event}. Review it in the staff console.", staff_link(row.makerspace, "stocktake"))


def render_stocktake(envelope):
    return stocktake_body(scoped(StocktakeSession, envelope.makerspace_id).get(pk=envelope.source_id), envelope.event)


@safe_notification
def notify_stocktake(row, event):
    # Reuses the existing stock category, matching the legacy personal inbox.
    return fanout(row=row, space=row.makerspace, feature="stock", stream="stocktake", event=event,
        source_kind=STOCKTAKE, revision=stocktake_revision(row, event), staff_body=stocktake_body(row, event))


def failure_eligible(envelope):
    row = scoped(EmailLog, envelope.makerspace_id).filter(pk=envelope.source_id).first()
    return bool(row and row.status == "failed" and row.attempts >= 1 and row.event != "email.failed"
        and envelope.audience == "staff" and envelope.event == "email.failed"
        and envelope.revision == revision(row.pk, "first_failure"))


@safe_notification
def notify_email_failure(log):
    if not log.makerspace_id or log.event == "email.failed" or log.attempts != 1 or log.status != "failed":
        return
    return fanout(row=log, space=log.makerspace, feature="api_access", stream="integrations", event="email.failed",
        source_kind=MAIL_FAILURE, revision=revision(log.pk, "first_failure"), rooms=False,
        staff_body=body("Email delivery failed", f"Email log #{log.pk} delivery failed.", staff_link(log.makerspace, "email-log")))


def on_email_saved(sender, instance, **kwargs):
    # Never emit during portable fixture loading, nor recursively for this alert's
    # own failed transport. Emission has a savepoint and cannot break SMTP state.
    # Cheap pre-check first: every EmailLog save passes through here, and the
    # adapter opens a savepoint.
    if (not kwargs.get("raw") and instance.makerspace_id and instance.status == "failed"
            and instance.attempts == 1 and instance.event != "email.failed"):
        notify_email_failure(instance)


def register():
    from django.db.models.signals import post_save
    register_source(STOCKTAKE, NotificationSource(stocktake_eligible, render_stocktake))
    register_source(MAIL_FAILURE, NotificationSource(failure_eligible))
    post_save.connect(on_email_saved, sender=EmailLog, dispatch_uid="p2.email_first_failure", weak=False)
