"""Staff routes for shelf pointers: coverage, show/clear, locations and shelf checks (decision 331). No pose leaves."""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.list_options import StaffListPagination
from apps.admin_api.permissions import IsActiveStaff
from apps.devices import services_shelf_check as checks
from apps.devices import services_shelf_pointer as shelf
from apps.devices.serializers_shelf import (
    ShelfCheckDetailSerializer, ShelfCheckSerializer, ShelfCheckWriteSerializer, ShelfClearSerializer,
    ShelfCoverageRequestSerializer, ShelfCoverageResponseSerializer, ShelfLocationSerializer, ShelfResultSerializer,
    ShelfShowSerializer,
)
from apps.devices.openapi_adapter_staff import page
from apps.devices.views_adapter_admin import ERRORS, TAG
from apps.devices.views_adapter_admin_more import _valid


class ShelfCoverageView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Which targets a calibrated shelf pointer can light (staff only, no pose)",
                   request=ShelfCoverageRequestSerializer, responses={200: ShelfCoverageResponseSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        data = _valid(ShelfCoverageRequestSerializer, request.data)
        return Response({"results": shelf.coverage(request.user, makerspace_id, data["targets"])})


class ShelfShowView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Show on shelf: point or light the pointer at a target (audited, caps applied)",
                   request=ShelfShowSerializer, responses={201: ShelfResultSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        shelf.show(request.user, makerspace_id, **_valid(ShelfShowSerializer, request.data))
        return Response({"sent": 1}, status=201)


class ShelfClearView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Clear the shelf pointer (never capped or rate limited)",
                   request=ShelfClearSerializer, responses={201: ShelfResultSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        sent = shelf.clear(request.user, makerspace_id, **_valid(ShelfClearSerializer, request.data))
        return Response({"sent": len(sent)}, status=201)


class ShelfLocationListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Storage locations for a shelf walk, with pointer coverage",
                   parameters=[OpenApiParameter("prefix", str, description="Only locations starting with this text.")],
                   responses={200: ShelfLocationSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        rows = checks.locations(request.user, makerspace_id, request.query_params.get("prefix", "")[:80])
        return Response(ShelfLocationSerializer(rows, many=True).data)


class ShelfCheckListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Past shelf checks (paginated, newest first)",
                   responses={200: page("ShelfCheckPage", ShelfCheckSerializer), **ERRORS})
    def get(self, request, makerspace_id):
        paginator = StaffListPagination()
        page = paginator.paginate_queryset(checks.history(request.user, makerspace_id), request)
        return paginator.get_paginated_response(ShelfCheckSerializer(page, many=True).data)

    @extend_schema(tags=[TAG], summary="Save a shelf check (each location OK or needs attention, with a note)",
                   request=ShelfCheckWriteSerializer, responses={201: ShelfCheckDetailSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        data = _valid(ShelfCheckWriteSerializer, request.data)
        row = checks.record(request.user, makerspace_id, data["scope_label"], data["entries"])
        return Response(ShelfCheckDetailSerializer(row).data, status=201)


class ShelfCheckDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="One shelf check with every location's finding",
                   responses={200: ShelfCheckDetailSerializer, **ERRORS})
    def get(self, request, pk):
        return Response(ShelfCheckDetailSerializer(checks.detail(request.user, pk)).data)
