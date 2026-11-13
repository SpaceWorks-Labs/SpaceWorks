"""Copy an immutable event design into independently owned tenant-library artwork."""
from .studio_assets import image_ids, remap
from django.utils.translation import gettext
from copy import deepcopy
from uuid import uuid4
import hashlib
import json

from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from apps.audit.services import record
from apps.events import event_authority
from apps.events.event_permissions import EDIT_DETAILS
from apps.events.models_certificate_templates import EventCertificateArtwork, EventCertificateTemplateRevision
from apps.events import certificate_artwork_storage as storage
from apps.events.credentials.errors import ProgrammeConflict
from apps.makerspaces import limits
from .library import tenant_command, require_artworks
from .library_models import (EventCertificateLibraryTemplate as Template, EventCertificateLibraryRevision as Revision,
                             EventCertificateLibraryArtwork as Artwork, EventCertificateLibraryCommand as Command)
from . import print_storage


def capture(makerspace_id, *, actor, operation_id, expected_version, event_id, revision_id, name, template_id=None):
    if (template_id is None and expected_version != 0) or not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
        raise ValidationError(gettext("Use a new library template and a name of 1–120 characters."))
    digest = hashlib.sha256(json.dumps(["library_capture", event_id, revision_id, name.strip(), template_id, expected_version]).encode()).hexdigest()
    event = event_authority.get_event(actor, event_id, EDIT_DETAILS)
    if event.makerspace_id != makerspace_id:
        raise NotFound()
    source = EventCertificateTemplateRevision.objects.filter(pk=revision_id, event=event).first()
    if not source:
        raise NotFound()
    with tenant_command(makerspace_id, actor) as space:
        receipt = Command.objects.select_for_update().filter(makerspace=space, operation_id=operation_id).first()
        if receipt:
            if receipt.request_sha256 != digest:
                raise ProgrammeConflict(gettext("Operation ID was already used."), code="operation_conflict")
            if receipt.result.get("phase") == "applied":
                return receipt.result["response"]
        else:
            if template_id:
                template = Template.objects.select_for_update().filter(makerspace=space, pk=template_id).first()
                if not template:
                    raise NotFound()
                if template.version != expected_version:
                    raise ProgrammeConflict()
            else:
                template = Template.objects.create(makerspace=space, name=name.strip())
            receipt = Command.objects.create(makerspace=space, template=template, operation_id=operation_id,
                request_sha256=digest, result={"phase": "preparing", "resources": {}})
            record(actor, "event.certificate_library_capture_started", makerspace=space, target=template)
    parameters = deepcopy(source.parameters)
    ids = image_ids(parameters)
    artworks = list(EventCertificateArtwork.objects.filter(event=event, resource_id__in=ids, promoted_at__isnull=False))
    if ids != {str(row.resource_id) for row in artworks}:
        raise NotFound()
    if source.artwork_id and not any(row.pk == source.artwork_id for row in artworks):
        artworks.append(source.artwork)
    mapping, logo_id = {}, None
    for original in artworks:
        payload = storage.read_artwork(original.object_key, original.version_id, original.sha256)
        with tenant_command(makerspace_id, actor) as space:
            event_authority.require(actor, event, EDIT_DETAILS)
            receipt = Command.objects.select_for_update().get(pk=receipt.pk)
            if receipt.result.get("phase") == "applied":
                return receipt.result["response"]
            copied_id = receipt.result["resources"].get(str(original.resource_id))
            if copied_id:
                target = Artwork.objects.get(pk=copied_id, template_id=receipt.template_id)
            else:
                limits.add_storage(space, len(payload))
                target = Artwork.objects.create(template_id=receipt.template_id, size_bytes=len(payload),
                    sha256=original.sha256, object_key=f"events/certificate-library/{space.pk}/{uuid4()}.png")
                receipt.result["resources"][str(original.resource_id)] = target.pk
                receipt.save(update_fields=("result",))
                record(actor, "event.certificate_library_capture_reserved", makerspace=space, target=target)
        if not target.promoted_at:
            print_storage.put(target.object_key, payload, "image/png")
            with tenant_command(makerspace_id, actor) as space:
                target = Artwork.objects.select_for_update().get(pk=target.pk)
                if not target.promoted_at:
                    target.promoted_at = timezone.now()
                    target.save(update_fields=("promoted_at",))
                    record(actor, "event.certificate_library_capture_promoted", makerspace=space, target=target)
        mapping[str(original.resource_id)] = str(target.resource_id)
        if original.pk == source.artwork_id:
            logo_id = target.pk
    remap(parameters, mapping)
    with tenant_command(makerspace_id, actor) as space:
        receipt = Command.objects.select_for_update().get(pk=receipt.pk)
        if receipt.result.get("phase") == "applied":
            return receipt.result["response"]
        template = Template.objects.select_for_update().get(pk=receipt.template_id)
        if template_id:
            if template.version != expected_version:
                raise ProgrammeConflict()
            template.name, template.version = name.strip(), template.version+1
            template.save(update_fields=("name", "version"))
        require_artworks(receipt.template, parameters, logo_id)
        revision = Revision.objects.create(template=receipt.template, parameters=parameters, artwork_id=logo_id)
        response = {"id": receipt.template_id, "version": template.version, "name": template.name,
                    "revision_id": revision.pk, "parameters": parameters, "artwork_id": logo_id}
        receipt.result = {"phase": "applied", "response": response}
        receipt.save(update_fields=("result",))
        record(actor, "event.certificate_library_capture_completed", makerspace=space, target=receipt.template,
               meta={"revision_id": revision.pk, "artwork_count": len(artworks)})
        return response
