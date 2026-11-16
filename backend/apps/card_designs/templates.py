"""Card and certificate templates (SPEC section 10): built-in gallery, space templates, save-from-design, apply.

"Apply keeps the data-field bindings": the new document is the template's; every data field the OLD design bound that
the template does not place is appended (small, stacked in the front's bottom-left safe corner) so no binding is lost,
and the response names them in `unplaced_fields`.
"""
from copy import deepcopy
from uuid import NAMESPACE_URL, uuid4, uuid5

from django.db import transaction
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit

from . import designs
from .contrast import background_at, luminance, rgb
from .data_fields import tags_in
from .default_templates import CERTIFICATE_LOOKS, LABELS, THEMES, build, build_certificate
from .layout import asset_ids, normalize_document, sides
from .models import CardDesign, CardTemplate

LIMIT_KEY = "card_templates"  # decision 284: counted per space, default none
BUILTIN = "builtin:"
FIELD_PITCH_MM, FIELD_SIZE_PT = 5.0, 8


def stock_theme(document):
    """light | dark from the front background (the gallery filter)."""
    front = document["front"]
    return "dark" if luminance(background_at(front["background"], 0, 0, 1, 1)) < 0.35 else "light"


def row_dict(row, *, document=False):
    data = {"id": row.pk, "source": "space", "key": None, "name": row.name, "description": row.description,
            "kind": row.kind, "domain_hint": row.domain_hint, "stock": row.stock, "theme": row.theme,
            "orientation": "portrait" if row.document["front"]["page_height_mm"] >= row.document["front"]["page_width_mm"] else "landscape",
            "back_enabled": row.document.get("back_enabled", False), "updated_at": row.updated_at}
    if document:
        data["document"] = row.document
    return data


def builtin_rows(kind=None):
    """One row per built-in look and theme; documents are built on demand by `apply` (`builtin:<key>:<theme>`)."""
    rows = []
    for theme in THEMES:
        for key, label in LABELS.items():
            document = build(key, "member_cards", theme)
            row_kind = document.get("kind", "card")
            if kind and row_kind != kind:
                continue
            rows.append(_builtin_row(key, label, theme, document))
    if kind != "card":  # decision 315: the certificate looks sit in the same gallery, `kind: certificate`
        rows += [_builtin_row(key, label, theme, build_certificate(key, theme))
                 for theme in THEMES for key, label in CERTIFICATE_LOOKS.items()]
    return rows


def _builtin_row(key, label, theme, document):
    front = document["front"]
    return {"id": f"{BUILTIN}{key}:{theme}", "source": "builtin", "key": key, "name": label, "description": "",
            "kind": document.get("kind", "card"), "domain_hint": "", "stock": document["stock"], "theme": theme,
            "orientation": "portrait" if front["page_height_mm"] >= front["page_width_mm"] else "landscape",
            "back_enabled": document["back_enabled"], "updated_at": None}


def builtin_document(key, theme):
    """A built-in look as a gallery row WITH its document (cards and certificates): what the designer opens."""
    if key in CERTIFICATE_LOOKS:
        document, label = build_certificate(key, theme), CERTIFICATE_LOOKS[key]
    elif key in LABELS:
        document, label = build(key, "member_cards", theme), LABELS[key]
    else:
        raise NotFound()
    return {**_builtin_row(key, label, theme, document), "document": document}


def space_rows(space, kind=None, stock=None):
    rows = CardTemplate.objects.filter(makerspace=space)
    if kind:
        rows = rows.filter(kind=kind)
    if stock:
        rows = rows.filter(stock=stock)
    return [row_dict(row) for row in rows]


def get_row(space, pk):
    row = CardTemplate.objects.filter(makerspace=space, pk=pk).first()
    if row is None:
        raise NotFound()
    return row


def _audit(actor, action, space, row, meta):
    audit.record(actor, action, makerspace=space, target=row, meta={"template_id": row.pk, **meta})


@transaction.atomic
def create_from_design(actor, space, design, name, description=""):
    from apps.managed_hosting.extra_quotas import check_extra_quota_locked
    check_extra_quota_locked(space, LIMIT_KEY)
    document = designs.validated(space.pk, design.document, check_contrast=False, domain=design.domain)
    if document.get("source"):
        raise ValidationError({"design_id": gettext("A badge-designer design is converted to the free canvas before it can be a template.")})
    return _save(actor, space, name, description, document, design.domain, design.pk, "card_template.created")


@transaction.atomic
def create_from_document(actor, space, document, name, description=""):
    """Save a certificate document as a space template. Event artwork belongs to one event, so images are not kept."""
    from apps.managed_hosting.extra_quotas import check_extra_quota_locked
    check_extra_quota_locked(space, LIMIT_KEY)
    clean = normalize_document(document)
    if clean.get("kind") != "certificate":
        raise ValidationError({"document": gettext("Only a certificate design can be saved this way; save a card from its design.")})
    if asset_ids(clean):
        raise ValidationError({"document": gettext("Templates do not keep images. Remove them, save, then add them after applying.")})
    return _save(actor, space, name, description, clean, "", None, "card_template.created")


def _save(actor, space, name, description, document, domain_hint, source_design_id, action):
    name = (name or "").strip()
    if not name or len(name) > 80:
        raise ValidationError({"name": gettext("Name the template (up to 80 characters).")})
    if CardTemplate.objects.filter(makerspace=space, name__iexact=name).exists():
        raise ValidationError({"name": gettext("This space already has a template with that name.")})
    row = CardTemplate.objects.create(makerspace=space, name=name, description=(description or "")[:200],
                                      kind=document.get("kind", "card"), domain_hint=domain_hint or "",
                                      stock=document["stock"], theme=stock_theme(document), document=document,
                                      source_design_id=source_design_id)
    _audit(actor, action, space, row, {"kind": row.kind, "stock": row.stock, "design_id": source_design_id})
    return row


@transaction.atomic
def update(actor, space, row, *, name=None, description=None, document=None):
    row = CardTemplate.objects.select_for_update().get(pk=row.pk)
    changed = []
    if name is not None and name.strip() != row.name:
        if CardTemplate.objects.filter(makerspace=space, name__iexact=name.strip()).exclude(pk=row.pk).exists():
            raise ValidationError({"name": gettext("This space already has a template with that name.")})
        row.name = name.strip()[:80]
        changed.append("name")
    if description is not None:
        row.description = description[:200]
        changed.append("description")
    if document is not None:
        clean = designs.validated(space.pk, document, check_contrast=False)
        row.document, row.stock, row.kind, row.theme = clean, clean["stock"], clean.get("kind", "card"), stock_theme(clean)
        changed.append("document")
    if changed:
        row.save()
        _audit(actor, "card_template.updated", space, row, {"fields": ",".join(changed)})
    return row


@transaction.atomic
def delete(actor, space, row):
    _audit(actor, "card_template.deleted", space, row, {})
    row.delete()


@transaction.atomic
def duplicate(actor, space, row):
    from apps.managed_hosting.extra_quotas import check_extra_quota_locked
    check_extra_quota_locked(space, LIMIT_KEY)
    base = f"{row.name[:70]} copy"
    name, count = base, 1
    while CardTemplate.objects.filter(makerspace=space, name__iexact=name).exists():
        count += 1
        name = f"{base} {count}"
    return _save(actor, space, name, row.description, row.document, row.domain_hint, row.source_design_id,
                 "card_template.created")


def _fields_of(document):
    """Every data field a document binds: data_field layers and {{tags}} in text, spans and translations."""
    found = set()
    for side in sides(document):
        for layer in document[side]["layers"]:
            if layer.get("field"):
                found.add(layer["field"])
            texts = [layer.get("text", ""), *(span["text"] for span in layer.get("spans") or []),
                     *(layer.get("translations") or {}).values()]
            for text in texts:
                found.update(tags_in(text))
    return found


def _resolve(space, reference, theme, domain):
    if isinstance(reference, str) and reference.startswith(BUILTIN):
        key, _, chosen = reference[len(BUILTIN):].partition(":")
        return key, build(key, domain, chosen or theme)
    try:
        row = get_row(space, int(reference))
    except (TypeError, ValueError):
        raise ValidationError({"template": gettext("Choose a built-in or saved template.")}) from None
    return None, row.document


def _reid(document, design_id):
    """Fresh, stable layer and group ids for this design (two designs never share an id; re-applying is idempotent)."""
    def new(value):
        return str(uuid5(NAMESPACE_URL, f"spaceworks:apply:{design_id}:{value}"))
    for side in ("front", "back"):
        for layer in document[side]["layers"]:
            layer["id"] = new(layer["id"])
            if layer.get("group"):
                layer["group"] = new(layer["group"])
        for group in document[side].get("groups", []):
            group["id"] = new(group["id"])
    return document


def _append_fields(document, fields):
    """Append the unplaced data fields to the front, stacked up from the bottom-left safe corner."""
    front = document["front"]
    width, height = front["page_width_mm"], front["page_height_mm"]
    safe = document.get("guides", {}).get("safe_mm", 3.0)
    under = background_at(front["background"], width / 2, height - safe, width, height)
    colour = "#FFFFFF" if luminance(under) < 0.4 else "#142C2A"
    for index, field in enumerate(sorted(fields)):
        top = height - safe - (index + 1) * FIELD_PITCH_MM
        if top < safe:
            break
        front["layers"].append({
            "id": str(uuid4()), "kind": "data_field", "name": field.replace("_", " ").title()[:40], "field": field,
            "x_mm": safe, "y_mm": round(top, 2), "w_mm": round(min(40.0, width - 2 * safe), 2), "h_mm": FIELD_PITCH_MM - 0.5,
            "rotation": 0, "opacity": 100, "locked": False, "hidden": False, "group": None,
            "font_family": "Outfit", "font_weight": 500, "font_size_pt": FIELD_SIZE_PT, "align": "left",
            "valign": "middle", "colour": colour, "uppercase": False, "tracking_pt": 0, "line_height": 1.2,
            "shrink_to_fit": True})


@transaction.atomic
def apply(actor, space, design, reference, *, expected_revision, keep_fields=True, theme="light", acted_for=None):
    """Replace a design's document with a template's. Returns (design, unplaced_fields)."""
    if not (isinstance(reference, str) and reference.startswith(BUILTIN)):
        # M9: editing ONE design (an event co-organiser can) is not authority over the space's saved templates;
        # reading one needs the template authority itself, and a refusal is the same 404 as a missing row.
        from .template_access import space_for
        space_for(actor, space.pk)
    key, template = _resolve(space, reference, theme, design.domain)
    if template.get("kind", "card") != "card":
        raise ValidationError({"template": gettext("This template is for a different kind of design.")})
    document = _reid(deepcopy(template), design.pk)
    missing = sorted(_fields_of(design.document) - _fields_of(document)) if keep_fields else []
    placeable = [field for field in missing if any(
        layer.get("field") == field for side in sides(design.document) for layer in design.document[side]["layers"])]
    if placeable:
        _append_fields(document, placeable)
    document = normalize_document(document, check_contrast=False)
    saved = designs.save(actor, design, document, expected_revision=expected_revision, acted_for=acted_for)
    audit.record(actor, "card_design.template_applied", makerspace=space, target=saved,
                 meta={"design_id": saved.pk, "template": key or str(reference), "unplaced": len(placeable)})
    return saved, placeable
