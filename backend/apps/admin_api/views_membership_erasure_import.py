"""Staff routes for erasure requests (X29) and the member import (G18, #128 C-13).

`manage_members` in the space; each route 404s when its switch is off. The import reads
the uploaded file on the server (CSV, TSV or .xlsx, #123); the preview is a dry run that
writes nothing, the apply writes the whole file in one transaction.
"""
import json

from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api import bulk_import_members as planner
from apps.admin_api.bulk_import_members_apply import apply_members
from apps.admin_api.bulk_import_parsers import rows_from_upload
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_membership_l4 import (
    ErasureDecisionInputSerializer, ImportedMemberSerializer, StaffErasureSerializer,
)
from apps.admin_api.views_membership_l4_common import scoped_row, staff_space
from apps.admin_api.views_roles import ERRORS
from apps.makerspaces import membership_erasure
from apps.makerspaces.models import ImportedMember, MembershipErasureRequest

TAGS = ["Admin memberships"]
_PREVIEW = inline_serializer("MemberImportPreview", {
    "headers": serializers.ListField(child=serializers.CharField()), "mapping": serializers.DictField(),
    "suggested_mapping": serializers.DictField(), "counts": serializers.DictField(),
    "rows": serializers.ListField(child=serializers.DictField()), "total_rows": serializers.IntegerField()})
_RESULT = inline_serializer("MemberImportResult", {
    "batch_id": serializers.IntegerField(), "counts": serializers.DictField(),
    "rows": serializers.ListField(child=serializers.DictField())})


class MemberImportUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    # JSON objects in multipart form fields: {field: column} and the staff row choices.
    mapping = serializers.CharField(required=False, allow_blank=True)
    record_only_rows = serializers.CharField(required=False, allow_blank=True)
    skip_rows = serializers.CharField(required=False, allow_blank=True)


def _json(raw, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise ValidationError({"detail": "Mapping and row choices must be JSON."}) from exc


def _read(request):
    data = MemberImportUploadSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    upload = data.validated_data["file"]
    try:
        rows = rows_from_upload(upload)
    except ValueError as exc:
        raise ValidationError({"file": str(exc) or "The file could not be read."}) from exc
    headers = list(rows[0].keys()) if rows else []
    mapping = _json(data.validated_data.get("mapping"), None) or planner.suggest_mapping(headers)
    if not isinstance(mapping, dict) or "email" not in mapping:
        raise ValidationError({"mapping": "Choose which column holds the email address."})
    return upload, rows, headers, mapping, data.validated_data


class MemberImportPreviewView(APIView):
    permission_classes = [IsActiveStaff]
    parser_classes = [MultiPartParser]

    @extend_schema(tags=TAGS, summary="Preview a member import (dry run)",
                   description="Maps columns (a mapping is suggested), normalises rows and reports what would "
                               "be created, updated or skipped and why. Writes nothing. CSV, TSV or .xlsx, "
                               "parsed on the server.",
                   request={"multipart/form-data": MemberImportUploadSerializer}, responses={200: _PREVIEW, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "import")
        _upload, rows, headers, mapping, _data = _read(request)
        planned = planner.plan_rows(space, rows, mapping, existing=planner.existing_state(space))
        return Response(planner.preview_payload(headers, mapping, planned))


class MemberImportApplyView(APIView):
    permission_classes = [IsActiveStaff]
    parser_classes = [MultiPartParser]

    @extend_schema(tags=TAGS, summary="Apply a member import",
                   description="Creates pending memberships. Each is emailed an invitation unless marked "
                               "record only; nothing links to an account until the person signs in with "
                               "that verified email and accepts. Audited as membership.imported.",
                   request={"multipart/form-data": MemberImportUploadSerializer}, responses={200: _RESULT, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "import")
        upload, rows, _headers, mapping, data = _read(request)
        batch, results = apply_members(
            request.user, space, rows, mapping,
            record_only_rows=_json(data.get("record_only_rows"), []), skip_rows=_json(data.get("skip_rows"), []),
            file_name=getattr(upload, "name", ""), file_kind="xlsx" if upload.name.lower().endswith(".xlsx") else "csv")
        return Response({"batch_id": batch.pk, "counts": batch.counts, "rows": results})


class ImportedMemberListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Imported members waiting to accept, and record-only rows",
                   responses={200: ImportedMemberSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "import")
        rows = ImportedMember.objects.filter(makerspace=space).exclude(status=ImportedMember.Status.CANCELLED)
        return Response(ImportedMemberSerializer(rows.select_related("plan")[:500], many=True,
                                                 context={"request": request}).data)


class ErasureQueueView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Erasure requests in this space",
                   responses={200: StaffErasureSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "erasure")
        rows = MembershipErasureRequest.objects.filter(makerspace=space).select_related("membership__user")
        return Response(StaffErasureSerializer(rows[:200], many=True, context={"request": request}).data)


class ErasureDecisionView(APIView):
    permission_classes = [IsActiveStaff]
    decision = "approve"

    @extend_schema(tags=TAGS, summary="Decide an erasure request",
                   description="Approve: this space's membership data is anonymised and the membership ends; "
                               "money rows and the audit log are kept; the account is never deleted. Reject: "
                               "a note for the member is required. The member is told. Audited.",
                   request=ErasureDecisionInputSerializer,
                   responses={200: StaffErasureSerializer, 400: OpenApiResponse(description="Already decided."),
                              **ERRORS})
    def post(self, request, pk):
        row = scoped_row(request.user, MembershipErasureRequest.objects.all(), pk, "erasure")
        data = ErasureDecisionInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        decide = membership_erasure.approve if self.decision == "approve" else membership_erasure.reject
        row = decide(request.user, row, data.validated_data["note"])
        return Response(StaffErasureSerializer(row, context={"request": request}).data)
