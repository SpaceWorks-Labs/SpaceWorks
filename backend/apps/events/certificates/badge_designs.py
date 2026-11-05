from apps.audit.services import record
from apps.events.credentials.boundary import event_command, advance, require_version
from apps.events.credentials.models import EventCredentialCommand
from apps.events.credentials.errors import ProgrammeConflict
import hashlib
import json
from apps.events.event_permissions import EDIT_DETAILS
from .layout import CUSTOM_RANGE_MM, CUSTOM_STOCK, DESIGN_STOCKS, normalize_document
from .print_models import EventBadgeTemplateRevision


def validate_design(document, stock, *, event_id=None):
    from rest_framework.exceptions import ValidationError
    if stock not in DESIGN_STOCKS and stock != CUSTOM_STOCK:
        raise ValidationError({"stock": "Choose a named stock or a custom size."})
    result = normalize_document(document, badge=True)
    size = (result["page_width_mm"], result["page_height_mm"])
    if stock == CUSTOM_STOCK:
        low, high = CUSTOM_RANGE_MM
        if not all(low <= side <= high and abs(side * 10 - round(side * 10)) < 1e-6 for side in size):
            raise ValidationError({"stock": f"A custom size is {low}-{high} mm on each side, in 0.1 mm steps."})
    elif size != DESIGN_STOCKS[stock]:
        raise ValidationError({"stock": "The document must match the physical stock dimensions."})
    if not any(layer["type"] == "event_credential_qr" for layer in result["layers"]):
        raise ValidationError({"layers": "A desk badge requires its typed event check-in QR slot."})
    # A design can reference packaged vectors or promoted same-event artwork.
    # The HTTP document never carries a path, object key or external image URL.
    from .seed_artwork import packaged_resource
    from apps.events.models_certificate_templates import EventCertificateArtwork
    for layer in result["layers"]:
        if layer["type"] != "image":
            continue
        if event_id and EventCertificateArtwork.objects.filter(event_id=event_id,
                resource_id=layer["resource_id"], promoted_at__isnull=False).exists():
            continue
        packaged_resource(layer["resource_id"])
    return result


def save_design(event_id, *, actor, document, stock, operation_id, expected_version):
    result = validate_design(document, stock, event_id=event_id)
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
        validate_design(result, stock, event_id=event.pk)
        # Packaged IDs are preview-only. Persisted designs must first install
        # independent owned artwork; deployment seed updates cannot alter history.
        from apps.events.models_certificate_templates import EventCertificateArtwork
        images = {layer["resource_id"] for layer in result["layers"] if layer["type"] == "image"}
        owned = {str(pk) for pk in EventCertificateArtwork.objects.filter(event=event,
            resource_id__in=images, promoted_at__isnull=False).values_list("resource_id", flat=True)}
        if images - owned:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"document": "Install the default design before saving its artwork."})
        row = EventBadgeTemplateRevision.objects.create(event=event, document=result, stock=stock)
        row.event_version = advance(event)
        EventCredentialCommand.objects.create(event=event, actor=actor, operation_id=operation_id,
            request_sha256=digest, result={"id": row.pk, "event_version": row.event_version})
        record(actor, "event.badge_design_saved", makerspace=event.makerspace, target=row,
               meta={"stock": stock, "layers": len(result["layers"])})
        return row
