"""Report registry download dispatch, shared by tenant and aggregate views."""
from contextlib import nullcontext

from apps.operations import reports
from apps.tenant_migration.gate_runtime import tenant_write
from .report_request_contract import _export_format, _grain_param, _report_filters
from .report_exports import _csv_response, _xlsx_response
from .report_exports_provenance import actor_label, build_provenance, export_filters
from .views_report_helpers import _date_range, _makerspace_for_report_view
from .report_definitions_machines import MACHINE_REPORT_KEYS


def _export_response(request, definition, makerspace_id, *, platform_context=None):
    """Build the file through the canonical row path and stamp its provenance.

    Every input the builder saw is echoed into the provenance filters, so a reader of the
    file can tell what subset it is without the URL that produced it.
    """
    fmt = _export_format(request, definition)
    local_space = None
    if makerspace_id is not None:
        local_space = _makerspace_for_report_view(request.user, makerspace_id, definition.key)
    local_dates = bool(request.query_params.get("subject_kind") or definition.subject_kind or definition.key in {"member-retention", "membership-revenue"} | MACHINE_REPORT_KEYS)
    date_range = _date_range(request, local_space if local_dates else None)
    report_filters = _report_filters(request, definition.key)
    grain = _grain_param(request, definition)
    rows = reports.report_rows(
        definition.key, makerspace_id, date_range=date_range,
        actor=request.user,
        report_filters=report_filters, grain=grain,
        platform_context=platform_context,
    )
    provenance = build_provenance(
        definition.key, version=definition.version, makerspace_id=makerspace_id,
        generated_by=actor_label(request.user),
        filters=export_filters(date_range=date_range, report_filters=report_filters, grain=grain,
            extra={"timezone": local_space.timezone} if local_space and report_filters.get("subject_kind") else None),
    )
    from apps.audit.services import record
    # GET bypasses the request write gate; hold the service gate through audit commit.
    with tenant_write(local_space.pk) if local_space is not None else nullcontext():
        record(request.user, "report.downloaded", makerspace=local_space,
               meta={"report_key": definition.key, "format": fmt, "filters": provenance.filters})
    if fmt == "pdf":
        from django.http import HttpResponse
        from django.utils.module_loading import import_string
        if not definition.pdf_renderer_path:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("PDF is unavailable for this report.")
        response = HttpResponse(import_string(definition.pdf_renderer_path)(rows, provenance=provenance,
                                title=definition.title), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{definition.key}.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response
    if fmt == "xlsx":
        response = _xlsx_response(rows, f"{definition.key}.xlsx", provenance=provenance)
    else:
        response = _csv_response(rows, f"{definition.key}.csv", provenance=provenance)
    if definition.subject_kind or report_filters.get("subject_kind"):
        response["Cache-Control"] = "private, no-store"
    return response
