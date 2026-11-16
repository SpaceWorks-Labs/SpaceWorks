"""Idempotent seed copies with event-owned immutable bytes and revisions."""

from django.utils.translation import gettext
from copy import deepcopy
from hashlib import sha256
import json
from uuid import NAMESPACE_URL, uuid5

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from apps.events.credentials.boundary import event_command, advance, require_version
from apps.events.credentials.models import EventCredentialCommand
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.event_permissions import EDIT_DETAILS
from apps.events.models_certificate_templates import EventCertificateArtwork, EventCertificateTemplateRevision
from apps.makerspaces import limits

from . import print_storage
from .badge_designs import validate_design
from .print_models import EventBadgeTemplateRevision
from .seed_artwork import render_packaged
from .seeds import catalogue


def install_to_event(event_id, *, actor, seed_id, theme, kind, stock=None, expected_version=None, operation_id=None, seed_version=None):
    if kind not in ("certificate", "badge") or theme not in ("light", "dark"):
        raise ValidationError({"seed_id": gettext("Choose a certificate or badge seed and theme.")})
    if kind == "certificate" and stock is not None:
        raise ValidationError({"stock": gettext("Certificates do not use badge stock.")})
    candidates = catalogue(kind=kind, theme=theme, stock=stock)
    seed = next((row for row in candidates if row["seed_id"] == seed_id), None)
    if seed is None:
        raise ValidationError({"seed_id": gettext("Unknown default design.")})
    if seed_version is not None and seed_version != seed["seed_version"]:
        raise ProgrammeConflict(gettext("The default design changed. Reload it."), code="seed_version_changed")
    recipe = json.dumps([event_id, kind, seed_id, seed["seed_version"], theme, stock], separators=(",", ":"))
    operation = operation_id or uuid5(NAMESPACE_URL, "spaceworks:seed-install:" + recipe)
    request_digest = sha256(recipe.encode()).hexdigest()
    model = EventBadgeTemplateRevision if kind == "badge" else EventCertificateTemplateRevision

    def previous(event):
        receipt = EventCredentialCommand.objects.filter(event=event, operation_id=operation).first()
        if receipt:
            if receipt.request_sha256 != request_digest:
                raise ProgrammeConflict(gettext("Seed installation operation was already used."), code="operation_conflict")
            return model.objects.get(event=event, pk=receipt.result["id"])

    with event_command(event_id, actor=actor, permission=EDIT_DETAILS) as (event, actor):
        result = previous(event)
        if result:
            return result
        if expected_version is not None:
            require_version(event, expected_version)
        expected_version = event.version
    document = deepcopy(seed["document"])
    mapping = {}
    for resource in seed["resources"]:
        payload = render_packaged(resource["id"], width_mm=document["page_width_mm"],
                                  height_mm=document["page_height_mm"])
        digest = sha256(payload).hexdigest()
        resource_id = uuid5(operation, resource["id"])
        with event_command(event_id, actor=actor, permission=EDIT_DETAILS) as (event, actor):
            result = previous(event)
            if result:
                return result
            row = EventCertificateArtwork.objects.filter(event=event, resource_id=resource_id).first()
            if row is None:
                limits.add_storage(event.makerspace, len(payload))
                row = EventCertificateArtwork.objects.create(event=event, resource_id=resource_id,
                    object_key=f"events/certificate-artwork/{event.makerspace_id}/{resource_id}.png",
                    size_bytes=len(payload))
                record(actor, "event.certificate_seed_artwork_reserved", makerspace=event.makerspace,
                       target=row, meta={})
        # Ownership precedes I/O. A failed write remains quota- and purge-owned.
        # The conditional writer verifies the elected bytes on replay.
        print_storage.put(row.object_key, payload, "image/png")
        with event_command(event_id, actor=actor, permission=EDIT_DETAILS) as (event, actor):
            row = EventCertificateArtwork.objects.select_for_update().get(pk=row.pk, event=event)
            if not row.promoted_at:
                row.sha256, row.promoted_at = digest, timezone.now()
                row.save(update_fields=("sha256", "promoted_at"))
                record(actor, "event.certificate_artwork_promoted", makerspace=event.makerspace,
                       target=row, meta={"size_bytes": len(payload)})
            if row.sha256 != digest:
                raise ValidationError({"seed_id": gettext("Installed artwork differs from the packaged seed.")})
        mapping[resource["id"]] = str(row.resource_id)
    for layer in document["layers"]:
        if layer["type"] == "image":
            layer["resource_id"] = mapping[layer["resource_id"]]
    with event_command(event_id, actor=actor, permission=EDIT_DETAILS) as (event, actor):
        result = previous(event)
        if result:
            return result
        require_version(event, expected_version)
        if kind == "badge":
            result = model.objects.create(event=event, stock=stock,
                document=validate_design(document, stock, event_id=event.pk))
            action = "event.badge_design_saved"
        else:
            from apps.events.certificate_templates import issuance_layout
            from types import SimpleNamespace
            issuance_layout(SimpleNamespace(event_id=event.pk, parameters=document, artwork=None))
            result = model.objects.create(event=event, parameters=document)
            action = "event.certificate_template_saved"
        version = advance(event)
        EventCredentialCommand.objects.create(event=event, actor=actor, operation_id=operation,
            request_sha256=request_digest, result={"id": result.pk, "event_version": version})
        record(actor, action, makerspace=event.makerspace, target=result,
               meta={"seed_id": seed_id, "seed_version": seed["seed_version"], "theme": theme})
        return result
