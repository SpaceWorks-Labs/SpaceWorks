"""Staff API for the settings-authority layer (#101, #128 C-11).

* `grants` -- who may change each module's settings (per person). GET and PUT are the
  Space Manager's; PUT replaces one module's live grants with the named people.
* `locks` -- Space Manager locks on single settings. GET and PUT are the Space Manager's.
* `effective` -- what the CALLER may edit, per module and key: any staff member who is the
  Space Manager or one of the module managers here.

The space is resolved through rbac (`scope_by_action` / `resolve_scope`) on the servable
queryset, so another space is a 404, never a 403 that confirms it exists.
"""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.pii_presentation import PiiMaskingSerializerMixin
from apps.admin_api.permissions import IsActiveStaff
from apps.openapi_errors import errors

from .models import Makerspace
from .models_settings_authority import ModuleSettingLock, ModuleSettingsGrant
from .servability import servable_queryset
from .settings_authority import is_space_manager
from .settings_authority_effective import effective, visible_modules
from .settings_authority_registry import MODULE_MANAGER_ACTIONS
from .settings_authority_writes import set_grants, set_lock

TAGS = ["Admin settings authority"]
_SM_ONLY = OpenApiResponse(description="Only this space's Space Manager (or the superadmin).")
_NOT_FOUND = OpenApiResponse(description="Makerspace not found or not visible to the caller.")


class GrantSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    pii_account_fields = ("grantee_name", "grantee_email")
    grantee_name = serializers.SerializerMethodField()
    grantee_email = serializers.SerializerMethodField()

    class Meta:
        model = ModuleSettingsGrant
        fields = ("id", "module", "grantee", "grantee_name", "grantee_email", "granted_by", "granted_at")
        read_only_fields = fields

    def get_grantee_name(self, obj) -> str:
        user = obj.grantee
        return (user.get_full_name() or user.username) if user else ""

    def get_grantee_email(self, obj) -> str:
        return obj.grantee.email if obj.grantee else ""


class CandidateSerializer(PiiMaskingSerializerMixin, serializers.Serializer):
    pii_account_fields = ("name", "email")
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    email = serializers.EmailField()

    def get_pii_makerspace_id(self, instance):
        return self.context["makerspace_id"]

    def get_pii_subject(self, instance):
        return instance

    def get_name(self, obj) -> str:
        return obj.get_full_name() or obj.username


class GrantsResponseSerializer(serializers.Serializer):
    grants = GrantSerializer(many=True)
    candidates = serializers.DictField(child=CandidateSerializer(many=True),
                                       help_text="Per module: the people who may be granted it here.")


class GrantsUpdateSerializer(serializers.Serializer):
    module = serializers.ChoiceField(choices=sorted(MODULE_MANAGER_ACTIONS))
    grantee_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=200)


class LockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleSettingLock
        fields = ("id", "setting_key", "note", "locked_by", "created_at")
        read_only_fields = fields


class LockUpdateSerializer(serializers.Serializer):
    setting_key = serializers.CharField(max_length=100)
    locked = serializers.BooleanField()
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class EffectiveKeySerializer(serializers.Serializer):
    key = serializers.CharField()
    editable = serializers.BooleanField()
    via = serializers.ChoiceField(choices=["space_manager", "module_grant", "fixed_exception"], allow_null=True)
    locked = serializers.BooleanField()
    code = serializers.ChoiceField(choices=["setting_not_delegated", "setting_locked"], allow_null=True)
    lock_note = serializers.CharField(allow_blank=True)


class EffectiveModuleSerializer(serializers.Serializer):
    module = serializers.CharField()
    space_manager = serializers.BooleanField()
    grant_id = serializers.IntegerField(allow_null=True)
    keys = EffectiveKeySerializer(many=True)


class EffectiveSerializer(serializers.Serializer):
    modules = EffectiveModuleSerializer(many=True)


def _space(actor, makerspace_id):
    return get_object_or_404(rbac.scope_by_visibility_or_action(
        actor, rbac.Action.MANAGE_MAKERSPACE, servable_queryset(Makerspace.objects.all()), field="id",
    ), pk=makerspace_id)


def _manager_space(actor, makerspace_id):
    space = _space(actor, makerspace_id)
    if not is_space_manager(actor, space):
        raise PermissionDenied(gettext("Only the Space Manager decides who may change settings."))
    return space


def _live_grants(space):
    return ModuleSettingsGrant.objects.filter(makerspace=space, revoked_at__isnull=True).select_related("grantee")


def _grants_payload(request, space):
    from .models import MakerspaceMembership
    from .settings_authority_writes import eligible_grantee

    # Candidates come from both tracks: staff rows hold the module roles.
    people = sorted({row.user for manager in (MakerspaceMembership.objects, MakerspaceMembership.staff_tracks)
                     for row in manager.filter(makerspace=space, status="active", user__is_active=True)
                     .select_related("user")}, key=lambda user: user.username)
    context = {"request": request, "makerspace_id": space.pk}
    return {
        "grants": GrantSerializer(_live_grants(space), many=True, context=context).data,
        "candidates": {module: CandidateSerializer(
            [user for user in people if eligible_grantee(space, module, user)], many=True, context=context).data
            for module in MODULE_MANAGER_ACTIONS},
    }


class SettingsGrantsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="List live per-person module settings grants",
                   responses={200: GrantsResponseSerializer, 403: _SM_ONLY, 404: _NOT_FOUND, **errors(401)})
    def get(self, request, makerspace_id):
        space = _manager_space(request.user, makerspace_id)
        return Response(_grants_payload(request, space))

    @extend_schema(
        tags=TAGS, summary="Replace one module's settings grants",
        description="Grants go to people who hold that module's manager action here and are not "
                    "already a Space Manager. Each grant created or revoked is audited.",
        request=GrantsUpdateSerializer,
        responses={200: GrantsResponseSerializer, 400: OpenApiResponse(description="Unknown module or ineligible person."),
                   403: _SM_ONLY, 404: _NOT_FOUND, **errors(401)})
    def put(self, request, makerspace_id):
        space = _manager_space(request.user, makerspace_id)
        body = GrantsUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        set_grants(request.user, space, body.validated_data["module"], body.validated_data["grantee_ids"])
        return Response(_grants_payload(request, space))


class SettingLocksView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="List live Space Manager setting locks",
                   responses={200: LockSerializer(many=True), 403: _SM_ONLY, 404: _NOT_FOUND, **errors(401)})
    def get(self, request, makerspace_id):
        space = _manager_space(request.user, makerspace_id)
        return Response(LockSerializer(ModuleSettingLock.objects.filter(
            makerspace=space, released_at__isnull=True), many=True).data)

    @extend_schema(
        tags=TAGS, summary="Lock or release one setting",
        description="A lock blocks every delegated edit of the key, the rental-timing exception "
                    "included; it never binds the Space Manager. Security settings are locked by "
                    "the platform elsewhere. Audited as settings.lock_created / settings.lock_released.",
        request=LockUpdateSerializer,
        responses={200: LockSerializer(many=True), 400: OpenApiResponse(description="Not a delegable setting."),
                   403: _SM_ONLY, 404: _NOT_FOUND, **errors(401)})
    def put(self, request, makerspace_id):
        space = _manager_space(request.user, makerspace_id)
        body = LockUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        set_lock(request.user, space, **body.validated_data)
        return Response(LockSerializer(ModuleSettingLock.objects.filter(
            makerspace=space, released_at__isnull=True), many=True).data)


class EffectiveSettingsAuthorityView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="What the caller may edit, per module and setting",
                   responses={200: EffectiveSerializer, 403: OpenApiResponse(
                       description="The caller manages no module here."), 404: _NOT_FOUND, **errors(401)})
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id)
        if not visible_modules(request.user, space):
            raise PermissionDenied()
        return Response(EffectiveSerializer(effective(request.user, space)).data)
