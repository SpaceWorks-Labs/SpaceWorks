"""L21b (X40): filtered staff event lists and their CSV exports, behind `events.saved_views`.

Filters are allow-listed per list (unknown keys answer 400). A saved view only restores these
filters; it never grants access, because both routes re-check the reader's event permission. The
export streams exactly the filtered rows (keyset chunks), neutralises spreadsheet formulas, and is
refused for a superadmin without an open PII window on the guest list (X-2). Every export is audited.
"""

import csv
from io import StringIO

from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit.services import record
from .judging.api_common import ERRORS, PrivateView, paginated
from .staff_list_specs import SPECS

PARAMS = [OpenApiParameter("list_key", str, OpenApiParameter.PATH, enum=sorted(SPECS)),
          *[OpenApiParameter(name, str, OpenApiParameter.QUERY) for name in
            ("q", "status", "state", "triage", "prize", "round", "below_target", "reply", "list",
             "collected", "page")]]
ListPage = inline_serializer(name="EventStaffListPage", fields={
    "count": serializers.IntegerField(), "next": serializers.URLField(allow_null=True),
    "previous": serializers.URLField(allow_null=True), "columns": serializers.ListField(child=serializers.CharField()),
    "results": serializers.ListField(child=serializers.DictField())})


PresetList = inline_serializer(name="EventStaffListPresets", fields={"results": serializers.ListField(
    child=inline_serializer(name="EventStaffListPreset", fields={
        "key": serializers.CharField(), "label": serializers.CharField(),
        "filters": serializers.DictField(child=serializers.CharField()), "count": serializers.IntegerField()}))})


def safe_cell(value):
    """Spreadsheet formula neutralisation: a leading = + - @ (after invisible prefixes) is quoted."""
    text = "" if value is None else "".join(c for c in str(value) if ord(c) >= 32 or c in "\t\r\n")
    if text.lstrip(" \t\r\n﻿​").startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def resolve(request, pk, list_key):
    from apps.events import event_authority
    from .judging.feature import SAVED_VIEWS, require_capability
    entry = SPECS.get(list_key)
    if entry is None:
        raise Http404
    spec, rows = entry
    event = event_authority.get_event(request.user, pk, spec.permission)
    require_capability(event, SAVED_VIEWS)
    params = {key: value for key, value in request.query_params.items() if key != "page"}
    unknown = set(params) - spec.filters
    if unknown:
        raise ValidationError({key: "Unknown filter for this list." for key in sorted(unknown)})
    return event, spec, rows, params


class EventStaffList(PrivateView):
    @extend_schema(tags=["Event staff lists"], parameters=PARAMS, responses={200: ListPage, **ERRORS},
                   description="One filtered staff list (guests, teams, submissions, results, progress); 24 per page.")
    def get(self, request, pk, list_key):
        from apps.accounts.pii_presentation import MASK, pii_visible
        event, spec, rows, params = resolve(request, pk, list_key)
        masked = spec.pii and not pii_visible(request.user, event.makerspace_id)
        values = [{**row, **({name: MASK for name in spec.pii} if masked else {})} for row in rows(event, params)]
        return paginated(request, values, None, columns=columns_for(spec, event),
                         **({"pii_masked": True} if masked else {}))


class EventStaffListPresets(PrivateView):
    @extend_schema(tags=["Event staff lists"], parameters=PARAMS[:1], responses={200: PresetList, **ERRORS},
                   description="Ready-made filters for the list with their counts (the guest list only, today).")
    def get(self, request, pk, list_key):
        from .staff_list_guests import presets
        event, spec, _rows, _params = resolve(request, pk, list_key)
        return Response({"results": presets(event) if spec.key == "guests" else []})


class EventStaffListExport(PrivateView):
    @extend_schema(tags=["Event staff lists"], parameters=PARAMS[:-1], responses={(200, "text/csv"): OpenApiTypes.STR,
                   **ERRORS}, description="Stream exactly the filtered rows as CSV. Guests need a PII window for a superadmin.")
    def get(self, request, pk, list_key):
        from apps.accounts.pii_presentation import require_pii_access
        from apps.operations.report_exports import StreamingCsvResponse
        from apps.tenant_migration.gate_runtime import tenant_write
        event, spec, rows, params = resolve(request, pk, list_key)
        if spec.pii:
            require_pii_access(request.user, event.makerspace_id)
        with tenant_write(event.makerspace_id):
            record(request.user, "event.export.csv", makerspace=event.makerspace, target=event,
                   meta={"event_id": event.pk, "list": spec.key, "filters": sorted(params)})
        response = StreamingCsvResponse(_lines(columns_for(spec, event), rows(event, params)),
                                        content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="event-{event.pk}-{spec.key}.csv"'
        return response


def columns_for(spec, event):
    return [*spec.columns, *(spec.extra_columns(event) if spec.extra_columns else ())]


def _lines(columns, rows):
    buffer = StringIO()
    writer = csv.writer(buffer)

    def flush():
        value = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()
        return value.encode("utf-8")
    writer.writerow(columns)
    yield flush()
    for row in rows:
        writer.writerow([safe_cell(row.get(column)) for column in columns])
        yield flush()
