"""Certificate signatories: freeze, preview and the render-time approval gate (C4).

Staff and signatory commands live in ``signatory_commands``; this module holds what issuance,
rendering and the designer call. A design prints a signatory through a ``signature`` layer
naming slot 1-3; issuance freezes that slot's name, title, image and version.
"""
from django.utils.translation import gettext
from django.db.models import Max

from apps.events.credentials.errors import ProgrammeConflict

SAMPLE = {1: ("Signatory name", "Director"), 2: ("Second signatory", "Programme lead"),
          3: ("Third signatory", "Partner")}


def printed_slots(parameters):
    if (parameters or {}).get("version") == 3:  # a Studio certificate: `signature` and `signature_row` layers
        from apps.card_designs.layout_certificate import printed_slots as studio_slots
        return studio_slots(parameters)
    return sorted({layer["signature_slot"] for layer in (parameters or {}).get("layers", ())
                   if layer.get("type") == "signature"})


def approval_required(event):
    from .models import EventCertificatePublicationPolicy
    return EventCertificatePublicationPolicy.objects.filter(event=event, signatory_approval_required=True).exists()


def current_designs(event):
    """The latest revision per certificate kind ("" = default): what issuance would use now."""
    from apps.events.models_certificate_templates import EventCertificateTemplateRevision
    rows = EventCertificateTemplateRevision.objects.filter(event=event)
    latest = rows.values("certificate_kind").annotate(latest=Max("pk")).values_list("latest", flat=True)
    return list(rows.filter(pk__in=list(latest)).order_by("certificate_kind"))


def validate_signature_layers(event, parameters):
    from .signatory_models import EventCertificateSignatory
    slots = printed_slots(parameters)
    known = set(EventCertificateSignatory.objects.filter(event=event, slot__in=slots).values_list("slot", flat=True))
    missing = [slot for slot in slots if slot not in known]
    if missing:
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"layers": gettext('Add signatory {value} before placing their signature.').format(value=missing[0])})


def _artwork(row):
    art = row.signature if row else None
    if art is None:
        return None
    return {"key": art.object_key, "version": art.version_id, "sha256": art.sha256}


def capture(event, layout):
    """Freeze the printed signatories into an issuance snapshot (inside the event lock)."""
    from .signatory_models import EventCertificateSignatory
    slots = printed_slots(layout)
    if not slots:
        return {}
    rows = {row.slot: row for row in EventCertificateSignatory.objects.select_related("signature").filter(
        event=event, slot__in=slots)}
    result = {}
    for slot in slots:
        row = rows.get(slot)
        if row is None:
            raise ProgrammeConflict(gettext("Signatory %(slot)s was removed. Update the certificate design.") % {"slot": slot},
                                    code="certificate_ineligible")
        result[str(slot)] = {"signatory_id": row.pk, "version": row.version, "name": row.name,
                             "title": row.title, "artwork": _artwork(row)}
    return result


def preview_signatures(event, snapshot):
    from .signatory_models import EventCertificateSignatory
    slots = printed_slots(snapshot)
    rows = {row.slot: row for row in EventCertificateSignatory.objects.select_related("signature").filter(
        event=event, slot__in=slots)}
    snapshot["signatures"] = {}
    for slot in slots:
        row = rows.get(slot)
        name, title = (row.name, row.title) if row else SAMPLE[slot]
        snapshot["signatures"][str(slot)] = {"signatory_id": row.pk if row else None,
                                             "version": row.version if row else 0, "name": name,
                                             "title": title, "artwork": _artwork(row)}
    return snapshot


def unapproved(event, template_revision_id, signatures):
    """Slots in a snapshot whose signatory has not approved this revision with those details."""
    from .signatory_models import EventCertificateSignatoryApproval
    if not signatures or not approval_required(event):
        return []
    waiting = []
    for slot, item in sorted(signatures.items()):
        if not EventCertificateSignatoryApproval.objects.filter(
                signatory_id=item.get("signatory_id"), template_revision_id=template_revision_id,
                signatory_version=item.get("version")).exists():
            waiting.append(int(slot))
    return waiting


def require_render_released(row):
    """A certificate renders (and is emailed) only after its printed signatories approved."""
    waiting = unapproved(row.event, row.template_revision_id, (row.layout_snapshot or {}).get("signatures"))
    if waiting:
        raise ProgrammeConflict(gettext("This certificate is waiting for its signatories to approve the design."),
                                code="signatory_approval_pending")


def design_status(event, revision):
    """Per printed slot of one revision: approved for the signatory's current details, or waiting."""
    from .signatory_models import EventCertificateSignatory, EventCertificateSignatoryApproval
    rows = {row.slot: row for row in EventCertificateSignatory.objects.filter(event=event)}
    result = []
    for slot in printed_slots(revision.parameters):
        row = rows.get(slot)
        approved = bool(row) and EventCertificateSignatoryApproval.objects.filter(
            signatory=row, template_revision=revision, signatory_version=row.version).exists()
        result.append({"slot": slot, "signatory_id": row.pk if row else None, "approved": approved})
    return result


def released(event, revision):
    if revision is None or not approval_required(event):
        return True
    return all(item["approved"] for item in design_status(event, revision))
