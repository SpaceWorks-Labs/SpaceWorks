"""Owner receipt metadata and staging uploads; receipt bytes are finance-only."""
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from .http import PrivateView, member_event, body
from .api_schema import ERRORS, TAGS, IDEMPOTENCY
from . import serializers as s, receipt_uploads as uploads


class ReceiptCreateView(PrivateView):
    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.ReceiptUploadCommand,
        responses={201: s.ReceiptUploadResult, **ERRORS})
    def post(self, request, makerspace_id, pk):
        event = member_event(request, pk, makerspace_id)
        return Response(uploads.create(request=request, event=event, data=body(request, s.ReceiptUploadCommand)), status=201)


class ReceiptDetailView(PrivateView):
    @extend_schema(tags=TAGS, responses={200: s.ReceiptMetadata, **ERRORS})
    def get(self, request, makerspace_id, pk, asset_id):
        event = member_event(request, pk, makerspace_id)
        return Response(uploads.metadata(uploads.owned_asset(event=event, owner_id=request.user.pk, asset_id=asset_id)))

    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.Command, responses={200: s.ReceiptMetadata, **ERRORS})
    def delete(self, request, makerspace_id, pk, asset_id):
        event = member_event(request, pk, makerspace_id)
        return Response(uploads.delete(request=request, event=event, asset_id=asset_id, data=body(request, s.Command)))


class ReceiptCompleteView(PrivateView):
    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.ReceiptCompleteCommand,
        responses={202: s.ReceiptCompleteResult, **ERRORS})
    def post(self, request, makerspace_id, pk, asset_id):
        event = member_event(request, pk, makerspace_id)
        return Response(uploads.complete(request=request, event=event, asset_id=asset_id,
            data=body(request, s.ReceiptCompleteCommand)), status=202)
