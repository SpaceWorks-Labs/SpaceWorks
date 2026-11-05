"""Registering OAuth apps for a space (#196): the Space Manager, or the superadmin for any space.

The client secret of a confidential app is shown once and stored hashed by
django-oauth-toolkit. Deleting an app (or switching it off) ends every connection to it.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from oauth2_provider.generators import generate_client_secret
from oauth2_provider.models import get_application_model
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.api_client_views import THROTTLE, _visible_makerspace
from apps.admin_api.permissions import IsActiveStaff
from apps.apiclients.origin_validation import validate_exact_origins
from apps.audit import services as audit
from apps.openapi_errors import errors

from . import person_scopes
from .models_tokens import OAuthAppRegistration

TAGS = ["App connections"]


class OAuthAppSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="application.pk", read_only=True)
    name = serializers.CharField(source="application.name", max_length=255)
    client_id = serializers.CharField(source="application.client_id", read_only=True)
    client_type = serializers.ChoiceField(source="application.client_type", choices=("confidential", "public"))
    redirect_uris = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    allowed_scopes = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    is_active = serializers.BooleanField(default=True)
    created_at = serializers.DateTimeField(read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["redirect_uris"] = instance.application.redirect_uris.split()
        return data


class OAuthAppCreatedSerializer(OAuthAppSerializer):
    client_secret = serializers.CharField(read_only=True, allow_blank=True,
                                          help_text="Confidential apps only; shown once.")


def _clean(data):
    uris = []
    for uri in data["redirect_uris"]:
        if not uri.startswith("https://") and not uri.startswith("http://localhost"):
            raise ValidationError({"redirect_uris": "Use https:// redirect URIs (http://localhost for development)."})
        uris.append(uri.strip())
    unknown = set(data["allowed_scopes"]) - person_scopes.person_scope_vocabulary() - {"openid"}
    if unknown:
        raise ValidationError({"allowed_scopes": f"Unknown scope(s): {', '.join(sorted(unknown))}."})
    validate_exact_origins([uri.split("/", 3)[0] + "//" + uri.split("/", 3)[2] for uri in uris])
    return uris


class OAuthAppListCreateView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = THROTTLE["throttle_classes"]
    throttle_scope = THROTTLE["throttle_scope"]

    @extend_schema(tags=TAGS, summary="This space's registered apps",
                   responses={200: OAuthAppSerializer(many=True), **errors(401, 403, 404, 429)})
    def get(self, request, makerspace_id):
        space = _visible_makerspace(request.user, makerspace_id)
        rows = OAuthAppRegistration.objects.filter(makerspace=space).select_related("application").order_by("-pk")
        return Response(OAuthAppSerializer(rows, many=True).data)

    @extend_schema(tags=TAGS, summary="Register an app (OAuth 2.0 client) for this space",
                   request=OAuthAppSerializer, responses={201: OAuthAppCreatedSerializer, **errors(400, 401, 403, 404, 429)})
    def post(self, request, makerspace_id):
        space = _visible_makerspace(request.user, makerspace_id)
        data = OAuthAppSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        uris = _clean(values)
        Application = get_application_model()
        secret = generate_client_secret() if values["application"]["client_type"] == "confidential" else ""
        with transaction.atomic():
            application = Application.objects.create(
                name=values["application"]["name"], client_type=values["application"]["client_type"],
                authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE, redirect_uris=" ".join(uris),
                client_secret=secret, user=None, skip_authorization=False,
                algorithm=Application.RS256_ALGORITHM if _oidc() else Application.NO_ALGORITHM)
            row = OAuthAppRegistration.objects.create(application=application, makerspace=space,
                                                      allowed_scopes=values["allowed_scopes"],
                                                      is_active=values["is_active"], created_by=request.user)
            audit.record(request.user, "oauth_app.created", makerspace=space, target=application,
                         meta={"scopes": values["allowed_scopes"], "client_type": application.client_type})
        return Response({**OAuthAppSerializer(row).data, "client_secret": secret}, status=status.HTTP_201_CREATED)


def _oidc():
    from oauth2_provider.settings import oauth2_settings
    return bool(oauth2_settings.OIDC_ENABLED)


class OAuthAppDetailView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = THROTTLE["throttle_classes"]
    throttle_scope = THROTTLE["throttle_scope"]

    def _row(self, request, pk):
        row = get_object_or_404(OAuthAppRegistration.objects.select_related("application", "makerspace"),
                                application_id=pk)
        _visible_makerspace(request.user, row.makerspace_id)
        return row

    @extend_schema(tags=TAGS, summary="Change an app's scopes, redirect URIs or switch it off",
                   request=OAuthAppSerializer(partial=True), responses={200: OAuthAppSerializer, **errors(400, 401, 403, 404, 429)})
    def patch(self, request, pk):
        row = self._row(request, pk)
        data = OAuthAppSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        with transaction.atomic():
            if "redirect_uris" in values:
                row.application.redirect_uris = " ".join(_clean({"redirect_uris": values["redirect_uris"],
                                                                 "allowed_scopes": []}))
            if "name" in values.get("application", {}):
                row.application.name = values["application"]["name"]
            row.application.save()
            if "allowed_scopes" in values:
                _clean({"redirect_uris": [], "allowed_scopes": values["allowed_scopes"]})
                row.allowed_scopes = values["allowed_scopes"]
            if "is_active" in values:
                row.is_active = values["is_active"]
            row.save()
            audit.record(request.user, "oauth_app.updated", makerspace=row.makerspace, target=row.application,
                         meta={"scopes": row.allowed_scopes, "is_active": row.is_active})
        return Response(OAuthAppSerializer(row).data)

    @extend_schema(tags=TAGS, summary="Delete an app and end every connection to it", request=None,
                   responses={204: None, **errors(401, 403, 404, 429)})
    def delete(self, request, pk):
        row = self._row(request, pk)
        with transaction.atomic():
            audit.record(request.user, "oauth_app.deleted", makerspace=row.makerspace, target=row.application)
            row.application.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
