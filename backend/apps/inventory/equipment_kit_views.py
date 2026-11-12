"""Scoped staff template and immutable version management."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.inventory.equipment_kit_serializers import (
    KitArchiveInput, KitCreateInput, KitDetail, KitPublicationInput, KitSummary, KitSummaryPage, KitVersionInput,
)
from apps.inventory.equipment_kit_services import KitRevisionConflict, append_version, create_template, set_flag
from apps.inventory.models_equipment_proposals import EquipmentKitTemplate, EquipmentKitVersion
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace
from django.utils.translation import gettext


class RevisionConflict(APIException):
    status_code = 409
    default_code = "revision_changed"
    default_detail = "Kit changed; reload and retry."


class KitPage(PageNumberPagination):
    page_size = 24


def _maker(request, makerspace_id, action):
    rows = rbac.scope_by_action(request.user, action, Makerspace.objects.all(), field="id")
    maker = get_object_or_404(rows, pk=makerspace_id)
    require_module(maker, "staff_admin")
    require_action(request.user, action, maker.pk)
    return maker


def _detail(template):
    version = get_object_or_404(EquipmentKitVersion, template=template, version=template.current_version)
    return {**KitSummary(template).data, "lines": version.lines}


def _call(function, **kwargs):
    try:
        return function(**kwargs)
    except KitRevisionConflict as exc:
        raise RevisionConflict() from exc
    except DjangoValidationError as exc:
        raise ValidationError(gettext("Invalid kit.")) from exc
    except DatabaseError as exc:
        if (getattr(exc.__cause__, "sqlstate", None) or getattr(exc.__cause__, "pgcode", None)) == "55P03":
            raise RevisionConflict(gettext("Kit is busy; retry.")) from exc
        raise


ERRORS = {400: OpenApiResponse(description="Invalid kit."),
          401: OpenApiResponse(description="Authentication required."),
          403: OpenApiResponse(description="Forbidden."), 404: OpenApiResponse(description="Unavailable."),
          409: OpenApiResponse(description="Revision conflict or lock busy."),
          423: OpenApiResponse(description="Tenant frozen."),
          429: OpenApiResponse(description="Rate limit exceeded.")}


class KitTemplateListView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    # Explicit IDs: the auto names of this list and the detail GET collide (`_retrieve_2`),
    # which breaks generated native clients.
    @extend_schema(
        operation_id="api_v1_admin_makerspace_equipment_kits_list",
        parameters=[
            OpenApiParameter("page", int, OpenApiParameter.QUERY, description="One-based page number."),
            OpenApiParameter("include_archived", bool, OpenApiParameter.QUERY,
                             description="Include archived kits; requires EDIT_INVENTORY."),
        ],
        responses={200: KitSummaryPage, **ERRORS},
    )
    def get(self, request, makerspace_id):
        maker = _maker(request, makerspace_id, rbac.Action.VIEW_INVENTORY)
        include = request.query_params.get("include_archived", "").lower() == "true"
        if include:
            require_action(request.user, rbac.Action.EDIT_INVENTORY, maker.pk)
        rows = EquipmentKitTemplate.objects.filter(makerspace=maker).order_by("pk")
        if not include:
            rows = rows.filter(archived=False)
        page = KitPage()
        return page.get_paginated_response(KitSummary(page.paginate_queryset(rows, request), many=True).data)

    @extend_schema(request=KitCreateInput, responses={201: KitDetail, **ERRORS})
    def post(self, request, makerspace_id):
        maker = _maker(request, makerspace_id, rbac.Action.EDIT_INVENTORY)
        data = KitCreateInput(data=request.data)
        data.is_valid(raise_exception=True)
        template, _ = _call(create_template, actor=request.user, makerspace_id=maker.pk, **data.validated_data)
        return Response(_detail(template), status=status.HTTP_201_CREATED)


class KitTemplateDetailView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    @extend_schema(operation_id="api_v1_admin_makerspace_equipment_kit_retrieve",
                   responses={200: KitDetail, **ERRORS})
    def get(self, request, makerspace_id, kit_id):
        maker = _maker(request, makerspace_id, rbac.Action.VIEW_INVENTORY)
        template = get_object_or_404(EquipmentKitTemplate, makerspace=maker, pk=kit_id)
        if template.archived:
            require_action(request.user, rbac.Action.EDIT_INVENTORY, maker.pk)
        return Response(_detail(template))


class KitVersionCreateView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    @extend_schema(request=KitVersionInput, responses={201: KitDetail, **ERRORS})
    def post(self, request, makerspace_id, kit_id):
        maker = _maker(request, makerspace_id, rbac.Action.EDIT_INVENTORY)
        data = KitVersionInput(data=request.data)
        data.is_valid(raise_exception=True)
        template, _ = _call(append_version, actor=request.user, makerspace_id=maker.pk,
                            template_id=kit_id, **data.validated_data)
        return Response(_detail(template), status=status.HTTP_201_CREATED)


class KitFlagView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]
    field = None
    serializer_class: type[serializers.Serializer]

    def post(self, request, makerspace_id, kit_id):
        maker = _maker(request, makerspace_id, rbac.Action.EDIT_INVENTORY)
        data = self.serializer_class(data=request.data)
        data.is_valid(raise_exception=True)
        template = _call(set_flag, actor=request.user, makerspace_id=maker.pk, template_id=kit_id,
                         expected_revision=data.validated_data["expected_revision"],
                         field=self.field, value=data.validated_data[self.field])
        return Response(KitSummary(template).data)


class KitPublicationView(KitFlagView):
    field = "published_for_contexts"
    serializer_class = KitPublicationInput

    @extend_schema(request=KitPublicationInput, responses={200: KitSummary, **ERRORS})
    def post(self, request, makerspace_id, kit_id):
        return super().post(request, makerspace_id, kit_id)


class KitArchiveView(KitFlagView):
    field = "archived"
    serializer_class = KitArchiveInput

    @extend_schema(request=KitArchiveInput, responses={200: KitSummary, **ERRORS})
    def post(self, request, makerspace_id, kit_id):
        return super().post(request, makerspace_id, kit_id)
