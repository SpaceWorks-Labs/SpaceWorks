from apps.audit.services import record
from apps.events.credentials.boundary import event_command, advance, require_version
from apps.events.credentials.models import EventCredentialCommand
from apps.events.credentials.errors import ProgrammeConflict
import hashlib
import json
from apps.events.event_permissions import EDIT_DETAILS
from .layout import STOCKS, normalize_document
from .print_models import EventBadgeTemplateRevision


def validate_design(document, stock):
    from rest_framework.exceptions import ValidationError
    if stock not in STOCKS:
        raise ValidationError({"stock": "Choose a named stock."})
    result = normalize_document(document, badge=True)
    if (result["page_width_mm"], result["page_height_mm"]) != STOCKS[stock]:
        raise ValidationError({"stock": "The document must match the physical stock dimensions."})
    if not any(layer["type"] == "event_credential_qr" for layer in result["layers"]):
        raise ValidationError({"layers": "A desk badge requires its typed event check-in QR slot."})
    # Arbitrary image/URL imports cannot become event render resources.
    if any(layer["type"] == "image" for layer in result["layers"]):
        raise ValidationError({"layers": "Badge images use the typed photo and logo slots."})
    return result


def save_design(event_id, *, actor, document, stock, operation_id, expected_version):
    result = validate_design(document, stock)
    digest = hashlib.sha256(json.dumps(["badge_design", result, stock, expected_version], sort_keys=True).encode()).hexdigest()
    with event_command(event_id, actor=actor, permission=EDIT_DETAILS) as (event, actor):
        previous = EventCredentialCommand.objects.filter(event=event, operation_id=operation_id).first()
        if previous:
            if previous.actor_id != actor.pk or previous.request_sha256 != digest:
                raise ProgrammeConflict("Operation ID was already used.", code="operation_conflict")
            row = EventBadgeTemplateRevision.objects.get(pk=previous.result["id"], event=event)
            row.event_version = previous.result["event_version"]
            return row
        require_version(event, expected_version)
        row = EventBadgeTemplateRevision.objects.create(event=event, document=result, stock=stock)
        row.event_version = advance(event)
        EventCredentialCommand.objects.create(event=event, actor=actor, operation_id=operation_id,
            request_sha256=digest, result={"id": row.pk, "event_version": row.event_version})
        record(actor, "event.badge_design_saved", makerspace=event.makerspace, target=row,
               meta={"stock": stock, "layers": len(result["layers"])})
        return row
