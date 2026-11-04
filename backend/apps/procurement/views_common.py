"""Constants and query helpers shared by every procurement view submodule.

A neutral module on purpose. These used to live in `views_items.py`, which meant
`views_items_export` imported from `views_items` while `views_items` imported
`ToBuyExportView` back from `views_items_export` — a real cycle: importing the export module
directly (as a test or a tool does) raised
``ImportError: cannot import name 'ToBuyExportView' from partially initialized module``.
It only stayed hidden because the urlconf always happened to import `views_items` first.

The rule the split has to respect: submodules depend on this module and never on each other,
and `views.py` is the thin re-export barrel that names the public surface.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse

from apps.makerspaces.folded_capabilities import (
    TOBUY_KEYS, require_any_capability, require_capability, tobuy_key,
)
from apps.procurement.models import ToBuyItem
from apps.procurement.serializers import ErrorSerializer

# `procurement` stopped being a module key in #97: the list is switched per parent
# (`machines.tobuy` for printing rows, `inventory.tobuy` for hardware rows), and a route
# whose switch is off answers 404 while every row is kept.
DEFAULT_LIST_LIMIT = 200
MAX_LIST_LIMIT = 500


PROCUREMENT_ERROR_RESPONSES = {
    400: OpenApiResponse(ErrorSerializer, description="Invalid request."),
    401: OpenApiResponse(description="Authentication credentials were not provided."),
    403: OpenApiResponse(description="Permission denied."),
    404: OpenApiResponse(description=(
        "Not found, or the To-Buy switch for this row's parent (machines.tobuy / "
        "inventory.tobuy) is off for this makerspace."
    )),
}


STATUS_PARAM = OpenApiParameter(
    "status",
    OpenApiTypes.STR,
    OpenApiParameter.QUERY,
    enum=ToBuyItem.Status.values,
    description="Filter by procurement item status.",
)


KIND_PARAM = OpenApiParameter(
    "kind",
    OpenApiTypes.STR,
    OpenApiParameter.QUERY,
    enum=[ToBuyItem.Kind.HARDWARE, ToBuyItem.Kind.PRINTING],
    description="Stream to add to. Honored only for makerspace admins/superadmin; "
    "other roles are auto-tagged by role.",
)


def require_tobuy(makerspace):
    """404 unless at least one parent's To-Buy switch is on here."""
    return require_any_capability(makerspace, TOBUY_KEYS)


def require_item_switch(item):
    """404 when the switch owning this row's domain is off (the row is kept)."""
    return require_capability(item.makerspace, tobuy_key(item.kind))


def list_limit(request):
    raw = request.query_params.get("limit", DEFAULT_LIST_LIMIT)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LIST_LIMIT
    if value < 1:
        return DEFAULT_LIST_LIMIT
    return min(value, MAX_LIST_LIMIT)


def apply_status_filter(queryset, request):
    status = request.query_params.get("status")
    if status in ToBuyItem.Status.values:
        return queryset.filter(status=status)
    return queryset


def receipt_queryset_related(queryset):
    return queryset.select_related("created_by", "purchaser", "machine_type").prefetch_related(
        "receipts__uploaded_by"
    )
