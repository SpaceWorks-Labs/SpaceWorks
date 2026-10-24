"""Tenant library revisions. Copying always creates event-owned artwork keys."""

from contextlib import contextmanager
from copy import deepcopy
from uuid import uuid4
import hashlib
import json

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit.services import record
from apps.events import event_authority
from apps.events.programme_locks import fences
from apps.accounts.models import User
from apps.events.certificate_templates import normalize_certificate_template
from apps.events.credentials.boundary import event_command, require_version, advance
from apps.events.credentials.models import EventCredentialCommand
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.event_permissions import EDIT_DETAILS
from apps.events.models_certificate_templates import EventCertificateArtwork, EventCertificateTemplateRevision
from apps.events import certificate_artwork_storage as storage
from apps.makerspaces import limits
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.guards import require_feature_locked
from apps.tenant_migration.gate_runtime import boundary_tenant_write

from .library_models import (EventCertificateLibraryTemplate as Template, EventCertificateLibraryRevision as Revision,
                             EventCertificateLibraryArtwork as Artwork, EventCertificateLibraryCommand as Command)
from . import print_storage


@contextmanager
def tenant_command(makerspace_id, actor):
    with boundary_tenant_write(makerspace_id), transaction.atomic(), fences(
            tenant_ids=(makerspace_id,), account_ids=(actor.pk,)):
        actor = User.objects.get(pk=actor.pk)
        space = require_module_locked(makerspace_id, "events")
        # Tenant library never accepts an event-scoped helper grant.
        event_authority.require_tenant(actor, space)
        require_feature_locked(space.pk, "events.certificate_designer")
        yield space


def require_artworks(template, parameters, artwork_id):
    ids = {row["resource_id"] for row in parameters.get("layers", []) if row["type"] == "image"}
    rows = list(template.artworks.filter(promoted_at__isnull=False))
    available = {str(row.resource_id): row for row in rows}
    if ids - available.keys() or (artwork_id and not any(row.pk == artwork_id for row in rows)):
        raise ValidationError({"artwork_id": "Use promoted artwork owned by this library template."})


def save(makerspace_id, *, actor, operation_id, expected_version, name, parameters,
         template_id=None, artwork_id=None):
    normalized = normalize_certificate_template(parameters)
    name = name.strip()
    if not 1 <= len(name) <= 120:
        raise ValidationError({"name": "Use 1–120 characters."})
    digest = hashlib.sha256(json.dumps([template_id, name, normalized, artwork_id, expected_version], sort_keys=True).encode()).hexdigest()
    with tenant_command(makerspace_id, actor) as space:
        previous = Command.objects.filter(makerspace=space, operation_id=operation_id).first()
        if previous:
            if previous.request_sha256 != digest:
                raise ProgrammeConflict("Operation ID was already used.", code="operation_conflict")
            return previous.result
        if template_id:
            template = Template.objects.select_for_update().filter(pk=template_id, makerspace=space).first()
            if not template:
                raise NotFound()
            if template.version != expected_version:
                raise ProgrammeConflict()
            template.name, template.version = name, template.version + 1
            template.save(update_fields=("name", "version"))
        else:
            if expected_version != 0:
                raise ProgrammeConflict()
            template = Template.objects.create(makerspace=space, name=name)
        require_artworks(template, normalized, artwork_id)
        revision = Revision.objects.create(template=template, parameters=normalized, artwork_id=artwork_id)
        record(actor, "event.certificate_library_saved", makerspace=space, target=template,
               meta={"version": template.version, "revision_id": revision.pk})
        result = {"id": template.pk, "version": template.version, "name": template.name,
                  "revision_id": revision.pk, "parameters": normalized, "artwork_id": artwork_id}
        Command.objects.create(makerspace=space, template=template, operation_id=operation_id,
                               request_sha256=digest, result=result)
        return result


def copy_to_event(makerspace_id, *, actor, template_id, revision_id, event_id, operation_id, expected_version):
    from apps.events.services_certificate_templates import save_template
    digest = hashlib.sha256(json.dumps(["library_copy", makerspace_id, template_id, revision_id, expected_version]).encode()).hexdigest()
    with event_command(event_id, actor=actor, permission=EDIT_DETAILS) as (event, actor):
        if event.makerspace_id != makerspace_id:
            raise NotFound()
        event_authority.require_tenant(actor, event.makerspace)
        receipt = EventCredentialCommand.objects.filter(event=event, operation_id=operation_id).first()
        if receipt:
            if receipt.actor_id != actor.pk or receipt.request_sha256 != digest:
                raise ProgrammeConflict("Operation ID was already used.", code="operation_conflict")
            return EventCertificateTemplateRevision.objects.get(pk=receipt.result["id"], event=event)
        require_version(event, expected_version)
    with tenant_command(makerspace_id, actor):
        revision = Revision.objects.select_related("template", "artwork").filter(
            pk=revision_id, template_id=template_id, template__makerspace_id=makerspace_id).first()
        if not revision:
            raise NotFound()
        parameters = deepcopy(revision.parameters)
        require_artworks(revision.template, parameters, revision.artwork_id)
    # Preparation and immutable copying happen outside all row locks.
    images = {row["resource_id"] for row in parameters.get("layers", []) if row["type"] == "image"}
    sources = list(revision.template.artworks.filter(resource_id__in=images))
    if revision.artwork_id and not any(row.pk == revision.artwork_id for row in sources):
        sources.append(revision.artwork)
    mapping, logo = {}, None
    for source in sources:
        payload = storage.read_artwork(source.object_key, source.version_id, source.sha256)
        with event_command(event_id, actor=actor, permission=EDIT_DETAILS) as (event, actor):
            if event.makerspace_id != makerspace_id:
                raise NotFound()
            limits.add_storage(event.makerspace, len(payload))
            target = EventCertificateArtwork.objects.create(event=event, size_bytes=len(payload),
                object_key=f"events/certificate-artwork/{makerspace_id}/{uuid4()}.png")
            record(actor, "event.certificate_library_copy_reserved", makerspace=event.makerspace, target=target)
        print_storage.put(target.object_key, payload, "image/png")
        with event_command(event_id, actor=actor, permission=EDIT_DETAILS) as (event, actor):
            target.sha256, target.promoted_at = source.sha256, timezone.now()
            target.save(update_fields=("sha256", "promoted_at"))
            record(actor, "event.certificate_library_artwork_copied", makerspace=event.makerspace, target=target)
        mapping[str(source.resource_id)] = str(target.resource_id)
        if source.pk == revision.artwork_id:
            logo = target.pk
    for layer in parameters.get("layers", []):
        if layer["type"] == "image":
            layer["resource_id"] = mapping[layer["resource_id"]]
    with event_command(event_id, actor=actor, permission=EDIT_DETAILS) as (event, actor):
        if event.makerspace_id != makerspace_id:
            raise NotFound()
        event_authority.require_tenant(actor, event.makerspace)
        receipt = EventCredentialCommand.objects.filter(event=event, operation_id=operation_id).first()
        if receipt:
            if receipt.actor_id != actor.pk or receipt.request_sha256 != digest:
                raise ProgrammeConflict("Operation ID was already used.", code="operation_conflict")
            return EventCertificateTemplateRevision.objects.get(pk=receipt.result["id"], event=event)
        require_version(event, expected_version)
        result = save_template(event, actor=actor, parameters=parameters, artwork_id=logo)
        version = advance(event)
        EventCredentialCommand.objects.create(event=event, actor=actor, operation_id=operation_id,
                                             request_sha256=digest, result={"id": result.pk, "version": version})
        return result
