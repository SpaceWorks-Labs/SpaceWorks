"""Immutable audience proofs and replay-safe composer commands."""

import hashlib

from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from apps.events.broadcasts import authorize, recipients
from apps.events.event_permissions import MANAGE_REGISTRATIONS
from apps.events.models_broadcasts import EventBroadcast, EventBroadcastPreview
from apps.events.services_broadcasts import compose_locked
from apps.makerspaces.website_directory import public_url

from .broadcast_content import render_content
from .commands import ProgrammeConflict, execute_command, fingerprint


def delivery_revision(campaign):
    if campaign.render_schema_version == 1:
        return "1"
    return fingerprint({"subject": campaign.subject, "body": campaign.body,
        "design": campaign.design, "schema": campaign.render_schema_version,
        "statuses": sorted(campaign.statuses), "attendance": campaign.attendance})


def content_digest(campaign):
    event = campaign.event
    return fingerprint({"subject": campaign.subject, "body": campaign.body,
        "schema": campaign.render_schema_version, "design": campaign.design,
        "event": event.pk, "title": event.title, "starts_at": event.starts_at,
        "location": event.location, "public_token": str(event.public_token),
        "slug": event.makerspace.slug, "frontend_domain": event.makerspace.frontend_domain,
        "frontend_domain_status": event.makerspace.frontend_domain_status,
        "statuses": sorted(campaign.statuses), "attendance": campaign.attendance})


def audience_proof(campaign):
    """Hash sorted account IDs without persisting a private attendee list."""
    from django.db.models import Q, Subquery
    from apps.accounts import rbac
    from apps.makerspaces.models import MakerspaceMembership
    denied = rbac.scope_notification_policy(MakerspaceMembership.objects.all(),
        makerspace_id=campaign.makerspace_id).filter(~Q(status="active") | Q(receives_notifications=False))
    rows = recipients(campaign).exclude(pk__in=Subquery(denied.values("user_id")))
    digest = hashlib.sha256(content_digest(campaign).encode())
    count = 0
    for pk in rows.order_by("pk").values_list("pk", flat=True).distinct().iterator(chunk_size=200):
        digest.update(f":{pk}".encode())
        count += 1
    return count, digest.hexdigest()


def preview_context(campaign, actor):
    event = campaign.event
    return {"name": actor.get_full_name() or actor.username,
        "event_title": event.title, "event_date": event.starts_at.isoformat(),
        "event_location": event.location,
        "ticket_url": public_url(event.makerspace, "member", "events"),
        "event_url": public_url(event.makerspace, "events", str(event.public_token))}


def preview_response(preview, actor):
    campaign = preview.campaign
    authorize(campaign, actor)
    if preview.created_by_id != actor.pk:
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied()
    if preview.content_sha256 != content_digest(campaign):
        raise ProgrammeConflict("stale_version", "Event details changed. Create a fresh preview.")
    rendered = render_content(campaign, preview_context(campaign, actor), preview=True)
    mobile = render_content(campaign, preview_context(campaign, actor), width=360, preview=True)
    return {"id": preview.pk, "event_id": campaign.event_id, "version": campaign.version,
        "state": "ready" if campaign.status == "draft" else campaign.status,
        "allowed_actions": ["test", "schedule"] if campaign.status == "draft" else [],
        "preview_id": preview.pk, "revision": preview.revision,
        "recipient_count": preview.recipient_count, "subject": rendered["subject"],
        "text": rendered["text_body"], "desktop_html": rendered.get("html_body", ""),
        "mobile_html": mobile.get("html_body", "")}


def campaign_command(campaign, actor, command, payload, execute):
    authorize(campaign, actor)
    def locked_campaign(event):
        row = EventBroadcast.objects.select_for_update().get(pk=campaign.pk, event=event)
        row.event = event
        row.makerspace = event.makerspace
        authorize(row, actor)
        return row

    response = execute_command(event=campaign.event, actor=actor, command=command,
        payload={"campaign_id": campaign.pk, **payload}, expected_version=payload["expected_version"],
        operation_id=payload["operation_id"], permission=MANAGE_REGISTRATIONS,
        version_getter=lambda event: locked_campaign(event).version,
        execute=lambda event, locked_actor: execute(locked_campaign(event), locked_actor))
    authorize(EventBroadcast.objects.get(pk=campaign.pk, event_id=campaign.event_id), actor)
    return response


def create_composer(event, actor, values, operation_id):
    def create(locked, locked_actor):
        row = compose_locked(locked, locked_actor, values)
        return {"campaign_id": row.pk}
    response = execute_command(event=event, actor=actor, command="broadcast.create",
        payload=values, expected_version=0, operation_id=operation_id,
        permission=MANAGE_REGISTRATIONS, version_getter=lambda event: 0, execute=create)
    campaign = EventBroadcast.objects.get(pk=response["campaign_id"], event=event)
    authorize(campaign, actor)
    return campaign


def create_preview(campaign, actor, payload):
    def create(row, locked_actor):
        if row.status != "draft" or row.render_schema_version != 2:
            raise ValidationError("Only composer drafts can be previewed.")
        count, revision = audience_proof(row)
        preview = EventBroadcastPreview.objects.create(campaign=row, created_by=locked_actor,
            content_sha256=content_digest(row), revision=revision, recipient_count=count)
        record(locked_actor, "event.broadcast.previewed", makerspace=row.makerspace,
               target=row, meta={"preview_id": preview.pk, "count": count, "revision": revision})
        return {"preview_id": preview.pk}
    response = campaign_command(campaign, actor, "broadcast.preview", payload, create)
    preview = EventBroadcastPreview.objects.select_related("campaign__event__makerspace").get(
        pk=response["preview_id"], campaign=campaign)
    return preview_response(preview, actor)
