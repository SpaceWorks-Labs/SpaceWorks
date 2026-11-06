"""Native app registrations in the web superadmin console (#190, parity with /control/).

The public identities of the Space Works mobile apps (package / bundle id, signer digests
or App ID Prefix) the server accepts attested sign-ins from. Same validation as /control/
(``NativeAppRegistrationForm``), the same ``native_app.registration_updated`` audit row
(``via: console``, changed field names), and revoking settles every device grant the app
issued through ``revoke_registration``. Never deleted: revocation keeps the trail.
Superadmin only; writes need a recent re-authentication. Holds no secret.
"""

import json

from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apps.accounts.forms_native_apps import NativeAppRegistrationForm
from apps.accounts.models_devices import NativeAppRegistration
from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.openapi_errors import errors

TAGS = ["Platform mobile apps"]
WRITABLE = ("makerspace", "app_id", "platform", "environment", "verifier_config_key", "signing_identities",
            "min_supported_version", "status")


class NativeAppSerializer(serializers.ModelSerializer):
    approved_by = serializers.CharField(source="approved_by.username", read_only=True, default=None)

    class Meta:
        model = NativeAppRegistration
        fields = ("id", *WRITABLE, "approved_by", "revoked_at", "created_at", "updated_at")
        read_only_fields = ("id", "approved_by", "revoked_at", "created_at", "updated_at")
        validators = []  # types only here; the /control/ form below owns validation and uniqueness
        extra_kwargs = {"signing_identities": {"help_text": "Android: 1-5 SHA-256 distribution digests. Apple: one App ID Prefix."}}


def _save(request, row, body, *, created):
    data = {**model_to_dict(row, fields=WRITABLE), **{key: value for key, value in body.items() if key in WRITABLE}}
    if data.get("makerspace") is not None and hasattr(data["makerspace"], "pk"):
        data["makerspace"] = data["makerspace"].pk
    data["signing_identities"] = json.dumps(data.get("signing_identities") or [])
    was = row.status
    becoming_approved = data.get("status") == NativeAppRegistration.Status.APPROVED and was != data.get("status")
    data["approved_by"] = request.user.pk if becoming_approved else row.approved_by_id
    data["revoked_at"] = row.revoked_at
    form = NativeAppRegistrationForm(data=data, instance=row)
    if not form.is_valid():
        return Response({("non_field_errors" if key == "__all__" else key): list(messages)
                         for key, messages in form.errors.items()}, status=status.HTTP_400_BAD_REQUEST)
    row = form.save()
    audit.record(request.user, "native_app.registration_updated", makerspace=row.makerspace, target=row,
                 meta={"via": "console", "created": created, "changed_fields": sorted(form.changed_data)})
    if row.status == NativeAppRegistration.Status.REVOKED and was != row.status:
        from apps.accounts.services_native_apps import revoke_registration
        row = revoke_registration(row, actor=request.user)
    return Response(NativeAppSerializer(row).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class NativeAppListCreateView(RecentReauthenticationMixin, GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = NativeAppSerializer
    queryset = NativeAppRegistration.objects.select_related("approved_by").order_by("platform", "environment", "app_id")

    @extend_schema(tags=TAGS, summary="List the registered mobile app identities",
                   responses={200: NativeAppSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(NativeAppSerializer(page, many=True).data)

    @extend_schema(tags=TAGS, summary="Register a mobile app identity", request=NativeAppSerializer,
                   responses={201: NativeAppSerializer, **errors(400, 401, 403)})
    def post(self, request):
        body = NativeAppSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return _save(request, NativeAppRegistration(), body.validated_data, created=True)


class NativeAppDetailView(RecentReauthenticationMixin, GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = NativeAppSerializer
    http_method_names = ["patch", "options"]

    @extend_schema(tags=TAGS, summary="Change, approve or revoke a mobile app identity (revoking ends its device sign-ins)",
                   request=NativeAppSerializer, responses={200: NativeAppSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, pk):
        row = get_object_or_404(NativeAppRegistration, pk=pk)
        body = NativeAppSerializer(row, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        return _save(request, row, body.validated_data, created=False)
