"""Holder photo upload (programme and event cards), clean-up jobs, and wallet passes.

Member-card photos keep `member/makerspaces/<id>/member-card/photo`; the clean-up and
wallet routes serve all three kinds.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.openapi_errors import errors
from .serializers_openapi import PhotoDecisionResultSerializer, PhotoSetSerializer, PhotoUploadSerializer

from . import jobs, photo_cleanup, photos
from .holder_access import own_card
from .models import CardJob
from .serializers import CardJobLinkSerializer, CardJobSerializer

TAGS = ["My cards"]
PHOTO_ACTIONS = {"programme_card": "id_programme.card_photo_updated", "event_card": "event_card.photo_updated"}


class PhotoPresignSerializer(serializers.Serializer):
    content_type = serializers.ChoiceField(choices=("image/png", "image/jpeg", "image/webp"))


class PhotoFinalizeSerializer(serializers.Serializer):
    object_key = serializers.CharField(max_length=300)
    consent = serializers.BooleanField()


class JobRefSerializer(serializers.Serializer):
    job_id = serializers.IntegerField()


class MyCardPhotoView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "id_join_upload"  # attaching decodes and re-encodes the image: 12/hour

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.request.method == "PUT" else []

    def _card(self, request, kind, card_id):
        if kind not in PHOTO_ACTIONS:
            raise NotFound()
        return own_card(request.user, kind, card_id)[1]

    @extend_schema(tags=TAGS, summary="Start a card photo upload (staging presign only)",
                   request=PhotoPresignSerializer, responses={201: PhotoUploadSerializer, **errors(400, 401, 404, 503)})
    def post(self, request, kind, card_id):
        card = self._card(request, kind, card_id)
        data = PhotoPresignSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            return Response(photos.presign(card, data.validated_data["content_type"]), status=status.HTTP_201_CREATED)
        except StorageUnavailable:
            return storage_unavailable_response()

    @extend_schema(tags=TAGS, summary="Attach the uploaded photo (needs consent; re-encoded, metadata stripped)",
                   request=PhotoFinalizeSerializer, responses={200: PhotoSetSerializer, **errors(400, 401, 404, 503)})
    def put(self, request, kind, card_id):
        card = self._card(request, kind, card_id)
        data = PhotoFinalizeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            photos.finalize(request.user, kind, card, object_key=data.validated_data["object_key"],
                            consent=data.validated_data["consent"])
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response({"photo_set": True})

    @extend_schema(tags=TAGS, summary="Remove my card photo", request=None,
                   responses={200: PhotoSetSerializer, **errors(401, 404)})
    def delete(self, request, kind, card_id):
        card = self._card(request, kind, card_id)
        photos.remove(request.user, kind, card)
        return Response({"photo_set": False})


class MyCardPhotoCleanupView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Ask for a background clean-up of my photo (a job; nothing changes yet)",
                   request=None, responses={201: CardJobSerializer, **errors(400, 401, 404)})
    def post(self, request, kind, card_id):
        _spec, card = own_card(request.user, kind, card_id)
        return Response(CardJobSerializer(photo_cleanup.request(request.user, kind, card)).data, status=201)


class MyCardPhotoDecisionView(APIView):
    permission_classes = [IsAuthenticated]
    accept = True

    @extend_schema(tags=TAGS, summary="Use the cleaned photo (the original is deleted)", request=JobRefSerializer,
                   responses={200: PhotoDecisionResultSerializer, **errors(400, 401, 404)})
    def post(self, request, kind, card_id):
        _spec, card = own_card(request.user, kind, card_id)
        data = JobRefSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        job = jobs.get_any(request.user, data.validated_data["job_id"])
        if job.kind != CardJob.Kind.PHOTO_CLEANUP or job.targets != [card.pk]:
            raise NotFound()
        if self.accept:
            photo_cleanup.accept(request.user, kind, card, job)
        else:
            photo_cleanup.discard(request.user, job)
        return Response({"accepted": self.accept})


class MyCardPhotoDiscardView(MyCardPhotoDecisionView):
    accept = False

    @extend_schema(tags=TAGS, summary="Keep my original photo and discard the cleaned one", request=JobRefSerializer,
                   responses={200: PhotoDecisionResultSerializer, **errors(400, 401, 404)})
    def post(self, request, kind, card_id):
        return super().post(request, kind, card_id)


class MyCardWalletView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Add my card to Apple or Google Wallet (a job; poll it)", request=None,
                   responses={201: CardJobSerializer, **errors(400, 401, 404)})
    def post(self, request, kind, card_id, platform):
        from .wallet.service import request_pass
        spec, card = own_card(request.user, kind, card_id)
        if spec.standing(card) != "valid":
            raise ValidationError({"detail": "Only a valid card can go into a wallet."})
        _row, job = request_pass(request.user, kind, card, platform)
        return Response(CardJobSerializer(job).data, status=201)


class MyCardJobView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="One of my card jobs (photo clean-up or wallet pass)", request=None,
                   responses={200: CardJobSerializer, **errors(401, 404)})
    def get(self, request, pk):
        return Response(CardJobSerializer(jobs.get_any(request.user, pk)).data)


class MyCardJobResultView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="A short-lived link to my job's file (cleaned photo or pass)", request=None,
                   responses={200: CardJobLinkSerializer, **errors(400, 401, 404, 503)})
    def get(self, request, pk):
        job = jobs.get_any(request.user, pk)
        try:
            return Response({"url": jobs.result_link(request.user, job)})
        except StorageUnavailable:
            return storage_unavailable_response()
