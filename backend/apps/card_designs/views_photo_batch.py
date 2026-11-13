"""Bulk card-photo upload, matched by file name (D314c addendum), under `admin/makerspaces/<id>/card-photo-batches`.

Authority is the single-photo route's, per card kind (member cards MANAGE_MEMBER_CARDS, staff cards the staff-card
managers, event cards an organiser of the event); another tenant's batch is 404. Creating a batch needs the
staff member to confirm the holders agreed. See `photo_batch.py` for the flow and `photo_batch_intake.py` for the
upload guards (500 photos per batch, 8 MB each, zip-bomb checks, no nested archives).
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.openapi_errors import errors

from . import photo_batch as service, photo_batch_holders as roster
from .serializers_image_adapter import (BatchApplySerializer, BatchCreateSerializer, BatchFilesSerializer, BatchItemChoiceSerializer,
                                        BatchSerializer)

TAG = "Card photos (staff)"
_ERR = errors(400, 401, 403, 404, 503)


def _detail(batch, space, event):
    return Response(service.review(batch, space, event))


@extend_schema(tags=[TAG], summary="Start a bulk card-photo upload (confirm the holders agreed)",
               request=BatchCreateSerializer, responses={201: BatchSerializer, **_ERR})
class PhotoBatchCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, makerspace_id):
        data = BatchCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        space, event = roster.authorise(request.user, values["kind"], makerspace_id, values.get("event_id"))
        batch = service.create(request.user, space, values["kind"], event,
                               holders_consented=values["holders_consented"],
                               remove_backgrounds=values["remove_backgrounds"])
        response = _detail(batch, space, event)
        response.status_code = status.HTTP_201_CREATED
        return response


class PhotoBatchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="The review table: matched, ambiguous, unmatched and already-has-photo",
                   request=None, responses={200: BatchSerializer, **_ERR})
    def get(self, request, makerspace_id, batch_id):
        batch, space, event = service.get_batch(request.user, makerspace_id, batch_id)
        return _detail(batch, space, event)

    @extend_schema(tags=[TAG], summary="Cancel an open batch and delete its uploaded files", request=None,
                   responses={200: BatchSerializer, **_ERR})
    def delete(self, request, makerspace_id, batch_id):
        batch, space, event = service.get_batch(request.user, makerspace_id, batch_id)
        service.cancel(request.user, batch, space)
        return _detail(batch, space, event)


@extend_schema(tags=[TAG], summary="Add photos or a zip to an open batch",
               description="multipart/form-data, field `files` (repeat it). Up to 500 photos per batch, 8 MB each; "
                           "one zip and at most 600 MB of photos per request; a zip may hold at most 2000 entries "
                           "and 600 MB unpacked, with no nested archives.",
               request={"multipart/form-data": BatchFilesSerializer}, responses={200: BatchSerializer, **_ERR})
class PhotoBatchFilesView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, makerspace_id, batch_id):
        batch, space, event = service.get_batch(request.user, makerspace_id, batch_id)
        uploads = request.FILES.getlist("files")
        try:
            service.add_files(batch, space, event, uploads)
        except StorageUnavailable:
            return storage_unavailable_response()
        return _detail(batch, space, event)


@extend_schema(tags=[TAG], summary="Choose the person for a photo, or replace / keep / skip it",
               request=BatchItemChoiceSerializer, responses={200: BatchSerializer, **_ERR})
class PhotoBatchItemView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def patch(self, request, makerspace_id, batch_id, item_id):
        batch, space, event = service.get_batch(request.user, makerspace_id, batch_id)
        data = BatchItemChoiceSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        service.choose(batch, space, event, item_id, holder_id=values.get("holder_id"),
                       decision=values.get("decision"), set_holder="holder_id" in values)
        return _detail(batch, space, event)


@extend_schema(tags=[TAG], summary="Apply the batch: attach the chosen photos through the normal photo path",
               description="Runs in the background; poll the batch. Counts and audit: one row for the batch and one "
                           "per applied photo. `remove_backgrounds` queues an eraser job per applied photo.",
               request=BatchApplySerializer, responses={202: BatchSerializer, **_ERR})
class PhotoBatchApplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, makerspace_id, batch_id):
        batch, space, event = service.get_batch(request.user, makerspace_id, batch_id)
        data = BatchApplySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        batch = service.apply(request.user, batch, space, data.validated_data.get("remove_backgrounds"))
        response = _detail(batch, space, event)
        response.status_code = status.HTTP_202_ACCEPTED
        return response
