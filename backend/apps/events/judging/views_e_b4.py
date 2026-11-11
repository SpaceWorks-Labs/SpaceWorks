"""Parity E-B4 HTTP adapters: the scores CSV and results unpublish.

Mounted from `urls_e_b4.py` (the frozen `urls.py` route contract is not edited). Writes delegate to
workflows that hold the event lock, the command receipt and the audit row.
"""

import csv
from io import StringIO

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import exports, results_unpublish
from .api_common import ERRORS, PrivateView, admin_event, schema
from .boundary import audit
from .feature import SCORES_EXPORT, require_capability
from .serializers import CommandInput, ResultEnvelope


def _lines(columns, rows):
    from apps.events.views_staff_lists import safe_cell
    buffer = StringIO()
    writer = csv.writer(buffer)

    def flush():
        value = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()
        return value.encode("utf-8")
    writer.writerow([safe_cell(column) for column in columns])
    yield flush()
    for row in rows:
        writer.writerow([safe_cell(row.get(column)) for column in columns])
        yield flush()


class ScoresExport(PrivateView):
    @extend_schema(tags=["Event programme judging"], responses={(200, "text/csv"): OpenApiTypes.STR, **ERRORS},
                   parameters=[OpenApiParameter("round", int, OpenApiParameter.QUERY)],
                   description="Stream the judging scores as CSV: rank, reviews, raw and adjusted score, one "
                               "average per criterion and the judges who scored. Never comments, notes or emails. "
                               "Behind events.scores_export; judge names need personal-data access.")
    def get(self, request, pk):
        from apps.accounts.pii_presentation import pii_visible
        from apps.operations.report_exports import StreamingCsvResponse
        from apps.tenant_migration.gate_runtime import tenant_write
        event = admin_event(request, pk, "manage_hackathon")
        require_capability(event, SCORES_EXPORT)
        raw = request.query_params.get("round")
        if raw not in (None, "") and not str(raw).isdigit():
            raise ValidationError({"round": "Use a round id."})
        round_id = int(raw) if raw not in (None, "") else None
        columns = exports.scores_columns(event, round_id)
        rows = list(exports.scores_rows(event, round_id=round_id,
                                        names_visible=pii_visible(request.user, event.makerspace_id)))
        with tenant_write(event.makerspace_id):
            audit(event, request.user, "scores_exported", event, event_id=event.pk, round_id=round_id, rows=len(rows))
        response = StreamingCsvResponse(_lines(columns, rows), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="event-{event.pk}-judging-scores.csv"'
        return response


class ResultsUnpublish(PrivateView):
    @schema(request=CommandInput, response=ResultEnvelope,
            description="Withdraw the published results (expected_version is the published result's version). "
                        "Unsent announcements are cancelled; 409 not_published or results_in_use once prizes "
                        "were paid or claimed. Publish again to re-announce; nobody is emailed twice.")
    def post(self, request, pk):
        return Response(results_unpublish.unpublish(pk, actor=request.user, data=request.data))
