"""Dormant owner route provider; G mounts only with exact claim/origin policies."""
from uuid import UUID

from django.db import transaction
from django.utils.decorators import method_decorator
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.encryption.crypto import PiiUnavailable
from apps.encryption.write_fence import PiiWriteFenced

from . import assets, downloads, exports, intents, serializers as s
from .access import require_owner
from .errors import SavedDetailsError
from .prefill import prefill
from .workflow import change_detail, list_details

ERRORS = {code: s.SavedVaultErrorResponse for code in (400, 401, 403, 404, 409, 410, 413, 423, 429, 503)}
IDEMPOTENCY = OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True,
                               description="UUID; must equal command operation_id when present.")


class VaultThrottle(UserRateThrottle):
    rate = "60/min"
    scope = "account_saved_details"


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class OwnerView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [VaultThrottle]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if getattr(request, "api_client", None) is not None:
            raise SavedDetailsError("permission_denied", "Sign in with your own member account.", 403)
        require_owner(request.user.pk)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["Vary"] = "Authorization, Cookie"
        return response

    def handle_exception(self, exc):
        if isinstance(exc, PiiUnavailable):
            error = SavedDetailsError(getattr(exc, "code", "account_key_unavailable"),
                                      "Protected details are unavailable. Try again.", getattr(exc, "status_code", 503))
            response = super().handle_exception(error)
            if getattr(exc, "retry_after", None):
                response["Retry-After"] = exc.retry_after
            return response
        if isinstance(exc, PiiWriteFenced):
            exc = SavedDetailsError("pii_write_fenced", "Protected writes are temporarily paused.", 423)
        if isinstance(exc, ValidationError):
            return Response({"code": "invalid_input", "detail": "Check the highlighted fields.", "fields": exc.detail}, status=400)
        return super().handle_exception(exc)

    def command(self, schema, *, keyed=True):
        value = schema(data=self.request.data)
        value.is_valid(raise_exception=True)
        body = value.validated_data
        if keyed:
            try:
                operation = UUID(self.request.headers.get("Idempotency-Key", ""))
            except (ValueError, TypeError, AttributeError) as exc:
                raise SavedDetailsError("invalid_operation_id", "Supply a UUID Idempotency-Key.") from exc
            if "operation_id" in body and body["operation_id"] != operation:
                raise SavedDetailsError("invalid_operation_id", "The operation ID and Idempotency-Key must match.")
            return body, operation
        return body


class DetailsView(OwnerView):
    @extend_schema(responses={200: s.SavedVaultDetailsResponse, **ERRORS}, tags=["Saved details"])
    def get(self, request):
        return Response(list_details(request.user.pk))


class DetailView(OwnerView):
    @extend_schema(request=s.SavedVaultDetailPut, parameters=[IDEMPOTENCY], responses={200: s.SavedVaultDetailResponse, **ERRORS}, tags=["Saved details"])
    def put(self, request, field_key):
        body, _ = self.command(s.SavedVaultDetailPut)
        return Response(change_detail(request.user.pk, field_key, body))

    @extend_schema(request=s.SavedVaultCommand, parameters=[IDEMPOTENCY], responses={200: s.SavedVaultDetailResponse, **ERRORS}, tags=["Saved details"])
    def delete(self, request, field_key):
        body, _ = self.command(s.SavedVaultCommand)
        return Response(change_detail(request.user.pk, field_key, body, delete=True))


class PrefillView(OwnerView):
    @extend_schema(request=s.SavedVaultPrefillInput, responses={200: s.SavedVaultPrefillResponse, **ERRORS}, tags=["Saved details"],
                   description="Owner-only prefill for registration, application, role assignment or a typed stage response. "
                   "Stage contexts bind an existing response or an owner creation UUID and stage form; they never read DOB or return derivations.")
    def post(self, request):
        return Response(prefill(request.user.pk, self.command(s.SavedVaultPrefillInput, keyed=False)))


class IntentView(OwnerView):
    @extend_schema(responses={200: s.SavedVaultIntentResponse, **ERRORS}, tags=["Saved details"])
    def get(self, request, operation_uuid):
        return Response(intents.intent_status(request.user.pk, operation_uuid))


class ResumeCreateView(OwnerView):
    @extend_schema(request=s.SavedVaultResumeInput, parameters=[IDEMPOTENCY], responses={201: s.SavedVaultResumeResponse, **ERRORS}, tags=["Saved details"])
    def post(self, request):
        body, operation = self.command(s.SavedVaultResumeInput)
        return Response(assets.create_resume(request.user.pk, body, operation), status=201)


class ResumeDetailView(OwnerView):
    @extend_schema(responses={200: s.SavedVaultResumeResponse, **ERRORS}, tags=["Saved details"])
    def get(self, request, asset_id):
        return Response(assets.project(assets.owned_asset(request.user.pk, asset_id)))

    @extend_schema(request=s.SavedVaultCommand, parameters=[IDEMPOTENCY], responses={200: s.SavedVaultResumeResponse, **ERRORS}, tags=["Saved details"])
    def delete(self, request, asset_id):
        body, _ = self.command(s.SavedVaultCommand)
        return Response(assets.delete_resume(request.user.pk, asset_id, body))


class ResumeCompleteView(OwnerView):
    @extend_schema(request=s.SavedVaultCompleteInput, parameters=[IDEMPOTENCY], responses={202: s.SavedVaultResumeResponse, **ERRORS}, tags=["Saved details"])
    def post(self, request, asset_id):
        body, _ = self.command(s.SavedVaultCompleteInput)
        return Response(assets.complete_resume(request.user.pk, asset_id, body), status=202)


_PDF = OpenApiResponse(response={"type": "string", "format": "binary"}, description="Owner PDF stream; no redirect. Single range supported.")
_ZIP = OpenApiResponse(response={"type": "string", "format": "binary"}, description="Owner ZIP stream; no redirect. Expires in 24 hours.")


class ResumeDownloadView(OwnerView):
    @extend_schema(responses={(200, "application/pdf"): _PDF, (206, "application/pdf"): _PDF, 416: s.SavedVaultErrorResponse, **ERRORS}, tags=["Saved details"])
    def get(self, request, asset_id):
        return downloads.resume_download(request, asset_id)


class ExportCreateView(OwnerView):
    @extend_schema(request=s.SavedVaultEmptyInput, parameters=[IDEMPOTENCY], responses={202: s.SavedVaultExportResponse, **ERRORS}, tags=["Saved details"])
    def post(self, request):
        _, operation = self.command(s.SavedVaultEmptyInput)
        return Response(exports.create_export(request.user.pk, operation), status=202)


class ExportDetailView(OwnerView):
    @extend_schema(responses={200: s.SavedVaultExportResponse, **ERRORS}, tags=["Saved details"])
    def get(self, request, job_uuid):
        return Response(exports.project(downloads.own_export(request.user.pk, job_uuid)))


class ExportDownloadView(OwnerView):
    @extend_schema(responses={(200, "application/zip"): _ZIP, (206, "application/zip"): _ZIP, 416: s.SavedVaultErrorResponse, **ERRORS}, tags=["Saved details"])
    def get(self, request, job_uuid):
        return downloads.export_download(request, job_uuid)
