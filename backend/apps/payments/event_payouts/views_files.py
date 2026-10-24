"""Finance byte gateway and owner upload status; no applicant download action."""
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.response import Response
from .http import PrivateView, obligation, body
from . import serializers as s, serializers_files as f, file_commands, downloads
from .errors import require


class FinanceAttachmentDownloadView(PrivateView):
    @extend_schema(tags=["Event payouts"], parameters=[OpenApiParameter("Range", str, OpenApiParameter.HEADER)],
        description="Full browser session and live host VIEW_FINANCE. Purpose is resolved from the attachment. "
            "Private no-store binary attachment; GET and HEAD support a single byte range. No presigned GET URL.",
        responses={200: OpenApiResponse(bytes), 206: OpenApiResponse(bytes), **s.ERRORS})
    def get(self, request, makerspace_id, asset_id):
        require(not request.query_params, "invalid_fields", status=400)
        return downloads.response(request=request, makerspace_id=makerspace_id, asset_id=asset_id)


class PayeeFileCreateView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.PayeeFileCreateCommand, responses={201: f.FileCreated, **s.ERRORS})
    def post(self, request, obligation_id):
        obligation(request, obligation_id, owner=True)
        return Response(file_commands.create(request=request, obligation_id=obligation_id,
            data=body(request, f.PayeeFileCreateCommand)), status=201)


class PayeeFileDetailView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: f.FileStatus, **s.ERRORS})
    def get(self, request, obligation_id, asset_id):
        row = obligation(request, obligation_id, owner=True)
        return Response(file_commands.status(file_commands.payee_asset(row, asset_id)))

    @extend_schema(tags=["Event payouts"], request=f.FinanceFileCommand, responses={200: f.FileCompleted, **s.ERRORS})
    def delete(self, request, obligation_id, asset_id):
        obligation(request, obligation_id, owner=True)
        return Response(file_commands.mutate(request=request, obligation_id=obligation_id, asset_id=asset_id,
            data=body(request, f.FinanceFileCommand)))


class PayeeFileCompleteView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.FinanceFileCommand, responses={202: f.FileCompleted, **s.ERRORS})
    def post(self, request, obligation_id, asset_id):
        obligation(request, obligation_id, owner=True)
        return Response(file_commands.mutate(request=request, obligation_id=obligation_id, asset_id=asset_id,
            data=body(request, f.FinanceFileCommand), complete=True), status=202)
