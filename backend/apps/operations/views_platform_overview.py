"""Superadmin platform overview API (#183A): read and CSV export, both platform-only.

Both views require an active platform superadmin in a browser session (a native grant
is refused by the platform context). The export is audited at platform level; reads
are not, like every other analytics read.
"""

from django.utils.translation import gettext
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.operations.platform_overview_cache import read_or_schedule
from apps.operations.platform_overview_export import overview_csv
from apps.operations.platform_overview_window import PRESETS, resolve_window
from apps.operations.platform_scope import _platform_context_for_view
from apps.operations.serializers_platform_overview import (
    PlatformOverviewComputingSerializer, PlatformOverviewErrorSerializer, PlatformOverviewSerializer,
)

RETRY_AFTER_SECONDS = 5
PARAMS = {"period", "start", "end", "include_excluded"}
NO_STORE = {"Cache-Control": "private, no-store"}

PARAMETERS = [
    OpenApiParameter("period", OpenApiTypes.STR, enum=list(PRESETS), description="Default this_month. UTC periods."),
    OpenApiParameter("start", OpenApiTypes.DATE, description="First UTC day; custom period only."),
    OpenApiParameter("end", OpenApiTypes.DATE, description="Last UTC day, inclusive; custom period only."),
    OpenApiParameter("include_excluded", OpenApiTypes.BOOL,
                     description="Also count archived, not-serving (importing/aborted) and directory-hidden "
                                 "spaces. Default false."),
]
ERRORS = {code: PlatformOverviewErrorSerializer for code in (400, 401, 403, 429)}
COMPUTING = OpenApiResponse(PlatformOverviewComputingSerializer,
                            description="Still computing in the background; retry after Retry-After seconds.")
FAILED = OpenApiResponse(PlatformOverviewErrorSerializer, description="The computation failed; retry shortly.")


def _flag(raw, field):
    if raw in (None, "", "0", "false"):
        return False
    if raw in ("1", "true"):
        return True
    raise ValidationError({field: gettext("Use true or false.")})


def _request_args(request, allowed):
    if set(request.query_params) - allowed:
        raise ValidationError({"detail": gettext("Unknown query parameter.")})
    params = request.query_params
    window = resolve_window(params.get("period") or "this_month", params.get("start"), params.get("end"))
    return window, _flag(params.get("include_excluded"), "include_excluded")


def _pending(data):
    if data["status"] == "computing":
        return Response({"status": "computing", "retry_after_seconds": RETRY_AFTER_SECONDS}, status=202,
                        headers={**NO_STORE, "Retry-After": str(RETRY_AFTER_SECONDS)})
    return Response({"detail": gettext("The platform overview could not be computed. Try again shortly."),
                     "code": "overview_failed"}, status=503, headers=NO_STORE)


class PlatformOverviewView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(
        tags=["Platform overview"], summary="Get the superadmin platform overview", request=None,
        description=("Combined totals across every live makerspace with the per-space breakdown beside them, "
                     "per domain block (shown only where its module is on somewhere) and money per currency. "
                     "Counts and money only; no person data. Cached; heavy work runs in Celery."),
        parameters=[*PARAMETERS, OpenApiParameter("refresh", OpenApiTypes.BOOL, description="Recompute now.")],
        responses={200: PlatformOverviewSerializer, 202: COMPUTING, 503: FAILED, **ERRORS},
    )
    def get(self, request):
        _platform_context_for_view(request)
        window, include_excluded = _request_args(request, PARAMS | {"refresh"})
        data = read_or_schedule(window, include_excluded,
                                refresh=_flag(request.query_params.get("refresh"), "refresh"))
        if data["status"] != "ready":
            return _pending(data)
        return Response(PlatformOverviewSerializer(data).data, headers=NO_STORE)


class PlatformOverviewExportView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(
        tags=["Platform overview"], summary="Export the superadmin platform overview as CSV", request=None,
        description="The same figures as the overview, one row per figure. Every export is audited.",
        parameters=PARAMETERS,
        responses={(200, "text/csv"): OpenApiResponse(OpenApiTypes.STR, description="CSV file."),
                   202: COMPUTING, 503: FAILED, **ERRORS},
    )
    def get(self, request):
        _platform_context_for_view(request)
        window, include_excluded = _request_args(request, PARAMS)
        data = read_or_schedule(window, include_excluded)
        if data["status"] != "ready":
            return _pending(data)
        body, rows = overview_csv(data)
        audit.record(request.user, "platform.overview_exported", target_type="platform_overview", meta={
            "period": window.preset, "include_excluded": include_excluded,
            "spaces": len(data["spaces"]), "rows": rows,
        })
        response = HttpResponse(body, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="platform-overview-{window.preset}.csv"'
        response["Cache-Control"] = "private, no-store"
        return response
