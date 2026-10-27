from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.bulk_import_sheet import sheet_rows_from_upload
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_bulk import (
    BulkImportSheetResultSerializer,
    BulkImportSheetSerializer,
)
from apps.admin_api.views_bulk import _authorized_makerspace
from apps.audit import services as audit


class BulkImportSheetView(APIView):
    """Read an uploaded .xlsx so the Bulk Import panel can match its columns.

    Same gate as the rest of Bulk Import: the `bulk_import` module and EDIT_INVENTORY
    in this makerspace. Nothing is stored; the import job re-reads the file itself."""

    permission_classes = [IsActiveStaff]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=["Bulk import"],
        summary="Read the rows of an .xlsx file for bulk import column matching",
        request={"multipart/form-data": BulkImportSheetSerializer},
        responses={
            200: BulkImportSheetResultSerializer,
            400: OpenApiResponse(
                description="The bulk_import module is off, or the file is not an .xlsx, is unreadable, or is over the size, row or column limit."
            ),
            403: OpenApiResponse(description="No EDIT_INVENTORY permission in this makerspace."),
            404: OpenApiResponse(description="Makerspace not found."),
        },
    )
    def post(self, request, makerspace_id, *args, **kwargs):
        makerspace = _authorized_makerspace(request, makerspace_id)
        serializer = BulkImportSheetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rows = sheet_rows_from_upload(serializer.validated_data["file"])
        except ValueError as exc:
            raise ValidationError({"file": str(exc) or "Uploaded file could not be read."})
        audit.record(
            request.user,
            "inventory.bulk_import_sheet_read",
            makerspace=makerspace,
            target=makerspace,
            meta={"rows": len(rows), "columns": len(rows[0]) if rows else 0},
        )
        return Response({"rows": rows})
