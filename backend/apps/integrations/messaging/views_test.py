"""A diagnostic sends only to the authenticated administrator's own consented phone."""
from uuid import uuid4

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.audit.services import record
from apps.integrations.models import MessagingDelivery
from apps.openapi_errors import errors
from apps.tenant_migration.gate_runtime import tenant_write
from .dispatch import schedule_delivery
from .eligibility import eligibility, reserve_quota
from .projections import PROJECTION_KEYS, project_context
from .views_settings import settings_space


class MessagingTestThrottle(UserRateThrottle):
    scope = "messaging_test"
    rate = "5/hour"


class MessagingTestSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=["sms", "whatsapp"])
    feature = serializers.CharField(default="hardware_requests")
    event = serializers.CharField(default="accepted")

    def validate(self, attrs):
        if (attrs["feature"], attrs["event"], "staff") not in PROJECTION_KEYS:
            raise ValidationError("Select a reviewed staff event for the test template.")
        if self.initial_data.keys() - {"channel", "feature", "event"}:
            raise ValidationError("Only channel, feature and event are accepted; the recipient is always you.")
        return attrs


class MessagingTestResponseSerializer(serializers.Serializer):
    delivery_id = serializers.IntegerField()
    status = serializers.CharField()
    skip_reason = serializers.CharField()


class MessagingTestView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MessagingTestThrottle]

    @extend_schema(tags=["Messaging"], request=MessagingTestSerializer,
        description="Diagnostic to your own verified, consented phone. The chosen event must pass feature/matrix, channel, consent, suppression, template and quota gates.", responses={
        202: MessagingTestResponseSerializer, **errors(400, 401, 403, 404, 423, 429)})
    def post(self, request, makerspace_id):
        serializer = MessagingTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        space = settings_space(request.user, makerspace_id)
        values = serializer.validated_data
        with tenant_write(space.pk):
            row = MessagingDelivery.objects.create(makerspace=space, user=request.user,
                channel=values["channel"], feature=values["feature"], event=values["event"], audience="staff",
                event_key=f"test:{uuid4()}", source_type="messaging_test", source_id=str(request.user.pk),
                context=project_context(values["feature"], values["event"], "staff", {"makerspace": space}))
            reason = eligibility(row)
            if reason == "ok" and not reserve_quota(row):
                reason = "quota_exceeded"
            if reason != "ok":
                row.status = "suppressed" if reason == "suppressed" else "skipped"
                row.skip_reason = "" if reason == "suppressed" else reason
                row.save(update_fields=["status", "skip_reason"])
            record(request.user, "messaging.test_enqueued", makerspace=space, target=row,
                   meta={"fields": ["channel", "status", "skip_reason"]})
            if row.status == "pending":
                transaction.on_commit(lambda: schedule_delivery(row.pk), robust=True)
        return Response({"delivery_id": row.pk, "status": row.status, "skip_reason": row.skip_reason}, status=202)
