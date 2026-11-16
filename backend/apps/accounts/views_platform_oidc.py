"""Single sign-on (OIDC) providers in the web superadmin console (#190, parity with /control/).

List, add and change; never delete, for the same reason as /control/: deleting a provider
would orphan every linked sign-in that names it. Disable it instead. Every save is the
same audit row as /control/ (``platform.oidc_provider_saved``) with ``via=console``.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models_oidc import OidcProvider
from apps.accounts.oidc_provider_guards import oidc_change_refusal, proposed_row
from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.openapi_errors import errors

TAGS = ["Platform security"]
EDITABLE = ("slug", "display_name", "issuer", "jwks_url", "client_id", "is_enabled", "allow_auto_link")


class OidcProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = OidcProvider
        fields = ("id", *EDITABLE, "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


def _record(actor, provider, *, created, changed):
    audit.record(actor, "platform.oidc_provider_saved", target=provider,
                 meta={"via": "console", "created": created, "changed_fields": changed})


class OidcProviderListCreateView(RecentReauthenticationMixin, GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = OidcProviderSerializer

    @extend_schema(tags=TAGS, summary="List single sign-on (OIDC) providers",
                   responses={200: OidcProviderSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        page = self.paginate_queryset(OidcProvider.objects.all())
        return self.get_paginated_response(OidcProviderSerializer(page, many=True).data)

    @extend_schema(tags=TAGS, summary="Add a single sign-on (OIDC) provider", request=OidcProviderSerializer,
                   responses={201: OidcProviderSerializer, **errors(400, 401, 403)})
    def post(self, request):
        body = OidcProviderSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        provider = body.save()
        _record(request.user, provider, created=True, changed=sorted(body.validated_data))
        return Response(OidcProviderSerializer(provider).data, status=status.HTTP_201_CREATED)


class OidcProviderDetailView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Change a single sign-on (OIDC) provider (disable it rather than delete)",
                   request=OidcProviderSerializer, responses={200: OidcProviderSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, pk):
        provider = get_object_or_404(OidcProvider, pk=pk)
        body = OidcProviderSerializer(provider, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        # Same refusals as the /control/ form: never re-point linked sign-ins, never strand anyone.
        refusal = oidc_change_refusal(provider, proposed_row(provider, body.validated_data))
        if refusal:
            return Response({"detail": refusal, "code": "oidc_provider_change_refused"},
                            status=status.HTTP_400_BAD_REQUEST)
        changed =sorted(field for field, value in body.validated_data.items() if getattr(provider, field) != value)
        provider = body.save()
        _record(request.user, provider, created=False, changed=changed)
        return Response(OidcProviderSerializer(provider).data)
