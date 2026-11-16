"""Boundary validation for immutable planned kit lines."""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext


def normalize_lines(lines, products, makerspace_id):
    """Validate locked authoritative products; never calculate stock here."""
    if not isinstance(lines, list) or not 1 <= len(lines) <= 50:
        raise ValidationError(gettext("A kit requires between one and fifty lines."))
    normalized = []
    seen = set()
    for line in lines:
        if not isinstance(line, dict) or set(line) != {"product_id", "quantity_per_person", "kind"}:
            raise ValidationError(gettext("Invalid kit line."))
        product_id, quantity, kind = line["product_id"], line["quantity_per_person"], line["kind"]
        if (type(product_id) is not int or product_id <= 0 or product_id in seen
                or type(quantity) is not int or not 1 <= quantity <= 99
                or not isinstance(kind, str) or kind not in {"returnable", "consumable"}):
            raise ValidationError(gettext("Invalid kit line."))
        product = products.get(product_id)
        if product is None or product.makerspace_id != makerspace_id or product.is_archived:
            raise ValidationError(gettext("Invalid kit product."))
        if bool(product.is_consumable) != (kind == "consumable"):
            raise ValidationError(gettext("Kit line kind does not match its product."))
        seen.add(product_id)
        normalized.append({"product_id": product_id, "quantity_per_person": quantity, "kind": kind})
    return normalized


def public_safe(lines, products, makerspace_id, *, consumables_enabled, returnable_allowed):
    """The caller authorizes the source; any unsafe line hides the whole kit."""
    try:
        normalized = normalize_lines(lines, products, makerspace_id)
    except ValidationError:
        return False
    for line in normalized:
        product = products[line["product_id"]]
        if not product.is_public:
            return False
        if line["kind"] == "consumable":
            if not consumables_enabled:
                return False
        elif not returnable_allowed(product):
            return False
    return True
