"""Self-only test emails retain a live typed source on every attempt."""

from django.utils.translation import gettext
from datetime import timedelta

from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import APIException, Throttled, ValidationError

from apps.audit.services import record
from apps.events.broadcasts import authorize
from apps.events.models_broadcasts import EventBroadcastPreview
from apps.integrations.delivery_content import render
from apps.integrations.delivery_sources import DeliverySource, register
from apps.integrations.dispatch_outbox import dispatch_email
from apps.integrations.models import EmailLog

from .broadcast_content import render_content
from .broadcast_preview import campaign_command, content_digest, preview_context
from .commands import ProgrammeConflict


def test_self(campaign, actor, payload):
    def reserve(row, locked_actor):
        preview = EventBroadcastPreview.objects.filter(pk=payload["preview_id"], campaign=row,
                                                        created_by=locked_actor).first()
        if row.status != "draft" or preview is None or preview.content_sha256 != content_digest(row):
            raise ProgrammeConflict("stale_version", "Create a fresh preview before sending a test.")
        if not locked_actor.email_verified_at:
            raise ValidationError({"recipient": gettext("Verify your own email before sending a test.")})
        try:
            validate_email(locked_actor.email)
        except DjangoValidationError:
            raise ValidationError({"recipient": gettext("Your own verified email is required.")}) from None
        if EmailLog.objects.filter(makerspace=row.makerspace, recipient_id=locked_actor.pk,
                source_kind="events.broadcast_test", created_at__gte=timezone.now() - timedelta(hours=1)).count() >= 5:
            raise Throttled(detail=gettext("Limit of five self-tests per hour."))
        log = dispatch_email(makerspace=row.makerspace, to_email=locked_actor.email,
            recipient_id=locked_actor.pk, subject=gettext("Broadcast preview"), text_body="",
            feature="events", stream="events", event="broadcast", audience="staff",
            source_kind="events.broadcast_test", source_id=preview.pk)
        record(locked_actor, "event.broadcast.test_queued", makerspace=row.makerspace, target=row,
               meta={"preview_id": preview.pk, "outbox_id": log.pk})
        return {"id": log.pk, "event_id": row.event_id, "version": row.version,
            "state": log.status if log.status in {"failed", "skipped"} else "queued",
            "allowed_actions": [], "recipient": "self"}
    return campaign_command(campaign, actor, "broadcast.test", payload, reserve)


def prepare_test(log):
    preview = EventBroadcastPreview.objects.select_related("campaign__event__makerspace", "created_by").filter(
        pk=log.source_id, campaign__makerspace_id=log.makerspace_id, created_by_id=log.recipient_id).first()
    if preview is None or preview.created_by is None:
        return False
    campaign, actor = preview.campaign, preview.created_by
    if campaign.status == "cancelled" or not actor.email_verified_at or actor.email != log.to_email:
        return False
    try:
        authorize(campaign, actor)
        if preview.content_sha256 != content_digest(campaign):
            return False
        values = render_content(campaign, preview_context(campaign, actor))
    except APIException:
        return False
    render(log, subject=gettext("[Test] ") + values["subject"], text_body=values["text_body"],
           html_body=values.get("html_body", ""), to_email=actor.email)
    return True


def register_test_source():
    register("events.broadcast_test", DeliverySource(prepare_test, digestible=False))
