"""Owner receipt metadata and staging uploads; receipt bytes are finance-only."""
from collections.abc import Mapping
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty
from rest_framework.response import Response
from .http import PrivateView, member_event, body
from .api_schema import ERRORS, TAGS, IDEMPOTENCY
from . import serializers as s, receipt_uploads as uploads


def _upload_claim(request, event):
    # Validate only the binding here; the remaining command stays behind the gates.
    if not isinstance(request.data, Mapping):
        s.ReceiptUploadCommand(data=request.data).is_valid(raise_exception=True)
    field = s.ReceiptUploadCommand().fields["claim_uuid"]
    try:
        claim_uuid = field.run_validation(request.data.get("claim_uuid", empty))
    except ValidationError as exc:
        raise ValidationError({"claim_uuid": exc.detail}) from exc
    return uploads.owned_claim(event=event, owner_id=request.user.pk, claim_uuid=claim_uuid)


class ReceiptCreateView(PrivateView):
    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.ReceiptUploadCommand,
        responses={201: s.ReceiptUploadResult, **ERRORS})
    def post(self, request, makerspace_id, pk):
        event = member_event(request, pk, makerspace_id, owner_lookup=lambda event: _upload_claim(request, event))
        return Response(uploads.create(request=request, event=event, data=body(request, s.ReceiptUploadCommand)), status=201)


class ReceiptDetailView(PrivateView):
    @extend_schema(tags=TAGS, responses={200: s.ReceiptMetadata, **ERRORS})
    def get(self, request, makerspace_id, pk, asset_id):
        event = member_event(request, pk, makerspace_id, asset_id=asset_id)
        return Response(uploads.metadata(uploads.owned_asset(event=event, owner_id=request.user.pk, asset_id=asset_id)))

    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.Command, responses={200: s.ReceiptMetadata, **ERRORS})
    def delete(self, request, makerspace_id, pk, asset_id):
        event = member_event(request, pk, makerspace_id, asset_id=asset_id)
        return Response(uploads.delete(request=request, event=event, asset_id=asset_id, data=body(request, s.Command)))


class ReceiptCompleteView(PrivateView):
    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.ReceiptCompleteCommand,
        responses={202: s.ReceiptCompleteResult, **ERRORS})
    def post(self, request, makerspace_id, pk, asset_id):
        event = member_event(request, pk, makerspace_id, asset_id=asset_id)
        return Response(uploads.complete(request=request, event=event, asset_id=asset_id,
            data=body(request, s.ReceiptCompleteCommand)), status=202)
