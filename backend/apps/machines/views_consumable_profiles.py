"""Staff API: a machine type's consumable profile, and the machine-type template catalogue (decisions 341/343)."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.audit.services import record
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace

from . import consumable_profile_services as profiles
from .models import MachineType
from .models_consumable_profiles import MachineTypeTemplate
from .serializers_consumable_profiles import (
    ApplyMachineTypeTemplateResultSerializer, ApplyMachineTypeTemplateSerializer, ConsumableDefinitionSerializer,
    ConsumableDefinitionUpdateSerializer, MachineTypeTemplateSerializer,
)
from .template_apply import apply_template
from .template_spec import builtin_templates, catalogue, validate_spec

TAGS = ["Admin machines"]
ERRORS = {code: OpenApiResponse(description=text) for code, text in (
    (400, "Invalid input."), (403, "Outside your machine scope."), (404, "Not found."))}


def _ids(data):
    out = dict(data)
    for name in ("consumable_pool", "product"):
        if name in out and out[name] is not None and not hasattr(out[name], "pk"):
            raise ValidationError({name: gettext("Invalid link.")})
    return out


class ConsumableRemoveOutcomeSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=["deleted", "deactivated"])


class TypeConsumablesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="A machine type's consumable profile in this space",
                   responses={200: ConsumableDefinitionSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id, type_id):
        space, machine_type = profiles.space_and_type(request.user, makerspace_id, type_id)
        rows = profiles.profile(space, machine_type).select_related("consumable_pool", "product")
        return Response(ConsumableDefinitionSerializer(rows, many=True).data)

    @extend_schema(tags=TAGS, summary="Add a consumable to a machine type's profile",
                   request=ConsumableDefinitionSerializer, responses={201: ConsumableDefinitionSerializer, **ERRORS})
    def post(self, request, makerspace_id, type_id):
        space, machine_type = profiles.space_and_type(request.user, makerspace_id, type_id, write=True)
        payload = ConsumableDefinitionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = profiles.create(request.user, space, machine_type, _ids(payload.validated_data))
        return Response(ConsumableDefinitionSerializer(row).data, status=status.HTTP_201_CREATED)


class TypeConsumableDetailView(APIView):
    permission_classes = [IsActiveStaff]

    def _row(self, request, makerspace_id, type_id, pk):
        space, machine_type = profiles.space_and_type(request.user, makerspace_id, type_id, write=True)
        return get_object_or_404(profiles.profile(space, machine_type), pk=pk)

    @extend_schema(tags=TAGS, summary="Edit one consumable of a machine type's profile",
                   request=ConsumableDefinitionUpdateSerializer,
                   responses={200: ConsumableDefinitionSerializer, **ERRORS})
    def patch(self, request, makerspace_id, type_id, pk):
        row = self._row(request, makerspace_id, type_id, pk)
        payload = ConsumableDefinitionUpdateSerializer(row, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        return Response(ConsumableDefinitionSerializer(profiles.update(request.user, row,
                                                                       _ids(payload.validated_data))).data)

    @extend_schema(tags=TAGS, summary="Remove a consumable (switched off instead when jobs used it)",
                   request=None, responses={200: ConsumableRemoveOutcomeSerializer, **ERRORS})
    def delete(self, request, makerspace_id, type_id, pk):
        row = self._row(request, makerspace_id, type_id, pk)
        return Response({"outcome": profiles.remove(request.user, row)})


def _manager_space(actor, makerspace_id, *, write=False):
    space = get_object_or_404(Makerspace, pk=makerspace_id)
    require_module(space, "machines")
    if rbac.is_space_manager_identity(actor, space.pk):
        return space
    if not write and rbac.can(actor, rbac.Action.MANAGE_MACHINES, space.pk):
        return space  # Machine Managers read the catalogue to re-apply a template to a type they manage
    raise PermissionDenied() if write else NotFound()


class TemplateListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Machine-type templates: the built-in catalogue plus this space's own",
                   responses={200: MachineTypeTemplateSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = _manager_space(request.user, makerspace_id)
        include = request.query_params.get("include_inactive") == "1"
        return Response(MachineTypeTemplateSerializer(catalogue(space, include_inactive=include), many=True).data)

    @extend_schema(tags=TAGS, summary="Save a space template (a built-in key saves an editable copy)",
                   request=MachineTypeTemplateSerializer, responses={201: MachineTypeTemplateSerializer, **ERRORS})
    @transaction.atomic
    def post(self, request, makerspace_id):
        space = _manager_space(request.user, makerspace_id, write=True)
        payload = MachineTypeTemplateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        _validate(data["spec"])
        defaults = {name: data[name] for name in ("name", "description", "category", "icon", "spec", "is_active")}
        defaults["based_on"] = data["key"] if data["key"] in builtin_templates() else ""
        row, created = MachineTypeTemplate.objects.update_or_create(makerspace=space, key=data["key"],
                                                                     defaults=defaults)
        record(request.user, "machine_type_template.saved", makerspace=space, target=row,
               meta={"key": row.key, "created": created})
        rows = {item["key"]: item for item in catalogue(space, include_inactive=True)}
        return Response(MachineTypeTemplateSerializer(rows[row.key]).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


def _validate(spec):
    from django.core.exceptions import ValidationError as ModelValidationError
    try:
        validate_spec(spec)
    except ModelValidationError as exc:
        raise ValidationError(getattr(exc, "message_dict", None) or {"spec": exc.messages}) from exc


class TemplateDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Delete a space template (a customised built-in reverts to the shipped one)",
                   request=None, responses={204: None, **ERRORS})
    @transaction.atomic
    def delete(self, request, makerspace_id, key):
        space = _manager_space(request.user, makerspace_id, write=True)
        row = get_object_or_404(MachineTypeTemplate, makerspace=space, key=key)
        record(request.user, "machine_type_template.deleted", makerspace=space, target=row, meta={"key": key})
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TemplateApplyView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Apply a template: create a machine type, or add its consumables to one",
                   description="Writes the type (new custom types only) and its consumable profile; every other "
                               "wizard step's suggested values come back as `prefill` for the endpoints that own "
                               "them. Existing consumable keys are never overwritten.",
                   request=ApplyMachineTypeTemplateSerializer,
                   responses={201: ApplyMachineTypeTemplateResultSerializer, 200: ApplyMachineTypeTemplateResultSerializer, **ERRORS})
    def post(self, request, makerspace_id, key):
        space = _manager_space(request.user, makerspace_id)
        payload = ApplyMachineTypeTemplateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        machine_type = None
        if data["machine_type_id"]:
            machine_type = get_object_or_404(
                rbac.scope_verified_tenant(MachineType.objects.all(), space) | MachineType.objects.filter(
                    makerspace__isnull=True), pk=data["machine_type_id"])
        outcome = apply_template(request.user, space, key, machine_type=machine_type, name=data["name"],
                                 slug=data["slug"])
        machine_type = outcome.pop("machine_type")
        body = {**outcome, "machine_type_id": machine_type.pk}
        return Response(ApplyMachineTypeTemplateResultSerializer(body).data,
                        status=status.HTTP_201_CREATED if outcome["created_type"] else status.HTTP_200_OK)
