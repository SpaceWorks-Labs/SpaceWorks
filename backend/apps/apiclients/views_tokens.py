"""A person's own personal access tokens (#196): create (after MFA re-auth), list, revoke.

These are /api/v1/auth/ routes, which no token can ever reach (person_scopes), so a
token cannot mint, list or revoke tokens: only the person's own signed-in session can.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.audit import services as audit
from apps.openapi_errors import errors

from . import person_scopes
from .models_tokens import DEFAULT_TTL_DAYS, MAX_TTL_DAYS, PersonalAccessToken

TAGS = ["Personal access tokens"]
MFA_CLAIM_KEYS = ("mfa_source", "mfa_version", "mfa_method")


class AccessTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalAccessToken
        fields = ("id", "name", "scopes", "makerspace", "created_at", "expires_at", "last_used_at", "revoked_at")
        read_only_fields = fields


class AccessTokenCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    scopes = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    makerspace = serializers.IntegerField(required=False, allow_null=True,
                                          help_text="Required with staff scopes: the one space they apply to.")
    expires_in_days = serializers.IntegerField(min_value=1, max_value=MAX_TTL_DAYS, default=DEFAULT_TTL_DAYS)


class AccessTokenCreatedSerializer(AccessTokenSerializer):
    token = serializers.CharField(read_only=True, help_text="Shown once. Store it like a password.")

    class Meta(AccessTokenSerializer.Meta):
        fields = (*AccessTokenSerializer.Meta.fields, "token")
        read_only_fields = fields


class PersonScopeSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    group = serializers.CharField()
    needs_space = serializers.BooleanField()


class PersonScopeCatalogSerializer(serializers.Serializer):
    scopes = PersonScopeSerializer(many=True)
    staff_spaces = serializers.ListField(child=serializers.DictField(child=serializers.CharField()),
                                         help_text="Spaces where you hold a staff role: {id, name}.")


def require_person(user):
    from apps.accounts.surface_policy import PERSON_KIND, token_kind
    if token_kind(user) != PERSON_KIND:
        raise PermissionDenied("Only a person's account can hold access tokens.")


def staff_spaces(user):
    from apps.accounts.staff_identity import staff_makerspace_ids
    from apps.makerspaces.models import Makerspace
    return Makerspace.objects.filter(pk__in=staff_makerspace_ids(user)).order_by("name")


class PersonScopeCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Scopes I can give a token or an app, and my staff spaces",
                   responses={200: PersonScopeCatalogSerializer, **errors(401, 403)})
    def get(self, request):
        require_person(request.user)
        spaces = [{"id": str(space.pk), "name": space.name} for space in staff_spaces(request.user)]
        return Response({"scopes": person_scopes.catalog(), "staff_spaces": spaces})


class AccessTokenListCreateView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "person_token_manage"

    @extend_schema(tags=TAGS, summary="My personal access tokens",
                   responses={200: AccessTokenSerializer(many=True), **errors(401, 403, 429)})
    def get(self, request):
        require_person(request.user)
        rows = PersonalAccessToken.objects.filter(user=request.user)[:200]
        return Response(AccessTokenSerializer(rows, many=True).data)

    @extend_schema(
        tags=TAGS, summary="Create a personal access token (needs a recent re-authentication)",
        request=AccessTokenCreateSerializer, responses={201: AccessTokenCreatedSerializer, **errors(400, 401, 403, 429)},
        examples=[OpenApiExample("Read my own account for 30 days", request_only=True, value={
            "name": "Calendar sync", "scopes": ["account:read"], "expires_in_days": 30})],
    )
    def post(self, request):
        require_person(request.user)
        data = AccessTokenCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        spaces = {space.pk: space for space in staff_spaces(request.user)}
        space_id = values.get("makerspace")
        makerspace = spaces.get(space_id) if space_id is not None else None
        if space_id is not None and makerspace is None:
            raise ValidationError({"makerspace": "You hold no staff role in that space."})
        try:
            scopes = person_scopes.validate(values["scopes"], makerspace=makerspace, staff_space_ids=set(spaces))
        except ValueError as exc:
            raise ValidationError({"scopes": str(exc)}) from exc
        claims = {key: request.auth.get(key) for key in MFA_CLAIM_KEYS if hasattr(request.auth, "get")}
        with transaction.atomic():
            row, raw = PersonalAccessToken.issue(user=request.user, name=values["name"], scopes=scopes,
                                                 makerspace=makerspace, days=values["expires_in_days"],
                                                 mfa_claims=claims)
            audit.record(request.user, "access_token.created", makerspace=makerspace, target=row,
                         meta={"scopes": scopes, "expires_at": row.expires_at.isoformat()})
        response = Response({**AccessTokenSerializer(row).data, "token": raw}, status=status.HTTP_201_CREATED)
        response["Cache-Control"] = "private, no-store"  # a one-time secret: never cached
        return response


class AccessTokenRevokeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "person_token_manage"

    @extend_schema(tags=TAGS, summary="Revoke one of my access tokens", request=None,
                   responses={204: None, **errors(401, 403, 404, 429)})
    def delete(self, request, pk):
        row = get_object_or_404(PersonalAccessToken, pk=pk, user=request.user)
        if row.revoked_at is None:
            row.revoked_at = timezone.now()
            row.save(update_fields=["revoked_at"])
            audit.record(request.user, "access_token.revoked", makerspace=row.makerspace, target=row)
        return Response(status=status.HTTP_204_NO_CONTENT)
