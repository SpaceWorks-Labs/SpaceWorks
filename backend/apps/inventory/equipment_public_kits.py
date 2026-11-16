"""Published-kit projection with whole-kit public eligibility in the database."""
from django.db.models import BooleanField, F
from django.db.models.expressions import RawSQL
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination

from apps.inventory.models import InventoryProduct
from apps.inventory.models_equipment_proposals import EquipmentKitVersion
from apps.makerspaces.platform import feature_enabled, module_enabled


class PublicKitLine(serializers.Serializer):
    product_id = serializers.IntegerField()
    display_name = serializers.CharField()
    quantity_per_person = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=["returnable", "consumable"])


class PublicKit(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    version = serializers.IntegerField()
    lines = PublicKitLine(many=True)


class PublicKitPage(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PublicKit(many=True)


class Page(PageNumberPagination):
    page_size = 24


# The CASE prevents jsonb_array_elements from being applied to corrupt non-arrays.
# A malformed line cannot turn a hidden/missing product into a public projection.
_SAFE_KIT = """
CASE WHEN jsonb_typeof(inventory_equipmentkitversion.lines) = 'array'
THEN CASE WHEN jsonb_array_length(inventory_equipmentkitversion.lines) BETWEEN 1 AND 50
THEN NOT EXISTS (
 SELECT 1 FROM jsonb_array_elements(inventory_equipmentkitversion.lines) AS line(value)
 WHERE CASE
   WHEN CASE WHEN jsonb_typeof(line.value) = 'object'
     THEN (line.value - 'product_id' - 'quantity_per_person' - 'kind') <> '{}'::jsonb
     ELSE TRUE END
     OR jsonb_typeof(line.value->'product_id') IS DISTINCT FROM 'number'
     OR jsonb_typeof(line.value->'quantity_per_person') IS DISTINCT FROM 'number'
     OR COALESCE(line.value->>'product_id', '') !~ '^[1-9][0-9]{0,15}$'
     OR COALESCE(line.value->>'quantity_per_person', '') !~ '^[1-9][0-9]?$'
     OR COALESCE(line.value->>'kind', '') NOT IN ('returnable', 'consumable')
   THEN TRUE
   ELSE NOT EXISTS (
     SELECT 1 FROM inventory_inventoryproduct AS product
     WHERE product.id = (line.value->>'product_id')::bigint
       AND product.id <= 9007199254740991
       AND product.makerspace_id = %s AND product.is_public AND NOT product.is_archived
       AND ((line.value->>'kind' = 'returnable' AND NOT product.is_consumable AND %s)
         OR (line.value->>'kind' = 'consumable' AND product.is_consumable AND %s))
   )
 END
) AND NOT EXISTS (
 SELECT 1 FROM jsonb_array_elements(inventory_equipmentkitversion.lines) AS duplicate(value)
 GROUP BY duplicate.value->>'product_id' HAVING COUNT(*) > 1
) ELSE FALSE END ELSE FALSE END
"""


def eligible_versions(maker):
    return EquipmentKitVersion.objects.filter(
        template__makerspace=maker, template__published_for_contexts=True,
        template__archived=False, version=F("template__current_version"),
    ).annotate(_public_safe=RawSQL(
        _SAFE_KIT, [maker.pk, module_enabled(maker, "request_workflow")
                    and feature_enabled(maker, "loans.enabled"),
                    feature_enabled(maker, "inventory.consumables")],
        output_field=BooleanField(),
    )).filter(_public_safe=True).select_related("template").order_by("template_id")


def _products(maker, versions):
    """One product query for every line of every kit on the page."""
    ids = {line["product_id"] for version in versions for line in version.lines}
    return {p.pk: p for p in InventoryProduct.objects.filter(
        pk__in=ids, makerspace=maker, is_public=True, is_archived=False,
    ).only("id", "name", "is_consumable")} if ids else {}


def _projection(version, products):
    ids = [line["product_id"] for line in version.lines]
    if any(pk not in products for pk in ids) or len(ids) != len(set(ids)):
        raise NotFound()
    lines = []
    for line in version.lines:
        product = products[line["product_id"]]
        if bool(product.is_consumable) != (line["kind"] == "consumable"):
            raise NotFound()
        lines.append({"product_id": product.pk, "display_name": product.name,
                      "quantity_per_person": line["quantity_per_person"], "kind": line["kind"]})
    return {"id": version.template_id, "name": version.name, "version": version.version, "lines": lines}


def kit_page(request, maker):
    paginator = Page()
    versions = list(paginator.paginate_queryset(eligible_versions(maker), request))
    products = _products(maker, versions)
    return paginator.get_paginated_response([_projection(version, products) for version in versions])


def kit_detail(maker, kit_id):
    version = eligible_versions(maker).filter(template_id=kit_id).first()
    if version is None:
        raise NotFound()
    return _projection(version, _products(maker, [version]))
