"""Parity O-B2 applicant routes: edit and resubmit a request that was sent back, and the join-form photo upload.

Own requests only (another person's request is 404). The staff side is `admin_api/views_member_register_bulk.py`.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.card_designs.serializers_openapi import PhotoUploadSerializer
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.makerspaces import membership_join_fields
from apps.makerspaces.membership_admission_changes import resubmit
from apps.makerspaces.membership_admission_settings import settings_for
from apps.makerspaces.models import MembershipPlan, MembershipRequest
from apps.makerspaces.serializers_admission import AdmissionRequestSerializer
from apps.makerspaces.throttles import MemberImagePresignThrottle
from apps.makerspaces.views_admission import ERRORS, own_admission_space


class ResubmitSerializer(serializers.Serializer):
    application_answers = serializers.JSONField(required=False, allow_null=True)
    # {phone, state_code, photo:{object_key, content_type, consent}} per the plan's `join_fields` modes.
    join_fields = serializers.JSONField(required=False, allow_null=True)


class JoinPhotoPresignSerializer(serializers.Serializer):
    content_type = serializers.CharField(max_length=64)
    plan_id = serializers.IntegerField(required=False, allow_null=True)


class MemberRequestResubmitView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "membership_request"

    @extend_schema(tags=["Memberships"], summary="Edit and resubmit a request that was sent back for changes",
                   description="Only the applicant, only while the request is `changes_requested`. Once: the request "
                               "returns to the review queue (or to vouching). Audited as membership.request_resubmitted.",
                   request=ResubmitSerializer, responses={200: AdmissionRequestSerializer, **ERRORS})
    def patch(self, request, pk):
        row = get_object_or_404(MembershipRequest, pk=pk, user=request.user)
        own_admission_space(request.user, row.makerspace_id)
        data = ResubmitSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = resubmit(request.user, row, data.validated_data.get("application_answers"),
                       data.validated_data.get("join_fields"))
        return Response(AdmissionRequestSerializer(row).data)


class MemberJoinPhotoView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberImagePresignThrottle]

    @extend_schema(tags=["Memberships"], summary="Create an upload URL for the join-form photo (staging only)",
                   description="For a plan whose `join_fields.photo` is optional or required. Upload the image, then "
                               "send `{object_key, content_type, consent: true}` in `join_fields.photo`.",
                   request=JoinPhotoPresignSerializer, responses={201: PhotoUploadSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = own_admission_space(request.user, makerspace_id)
        data = JoinPhotoPresignSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        plan_id = data.validated_data.get("plan_id")
        plan = (MembershipPlan.objects.filter(makerspace=space, pk=plan_id, is_active=True).first()
                if plan_id else settings_for(space).default_plan)
        try:
            payload = membership_join_fields.presign_join_photo(space, plan, data.validated_data["content_type"])
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(payload, status=201)
