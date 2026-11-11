from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.audit import services as audit
from apps.boxes.access import makerspace_for_action
from apps.boxes.external_qr import assign_external_qr, clean_value, target_for
from apps.boxes.models import QrCode
from apps.boxes.serializers import QrCodeSerializer, qr_target_payload
from apps.boxes.serializers_external import (
    ExternalQrAssignResultSerializer,
    ExternalQrAssignSerializer,
    ExternalQrConflictSerializer,
)
from apps.inventory import availability
from apps.inventory.models import InventoryAsset, InventoryProduct, TrackingMode
from apps.makerspaces import limits
from apps.makerspaces.guards import require_module
from apps.openapi_errors import errors


class ExternalQrAssignView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["QR assets"],
        summary="Link a QR label printed outside SpaceWorks",
        description=(
            "Registers the raw value of a QR label printed elsewhere (trimmed, case preserved, "
            "at most 64 characters) against an existing product or asset unit, or against a "
            "new product / unit created in the same transaction. Requires `manage_qr`; "
            "creating also requires `edit_inventory`. Values are unique per makerspace across "
            "every status. 409 `already_assigned` returns the linked item and keeps the link; "
            "`revoked` means the label was retired here; `target_has_qr` means the item already "
            "has an active QR code. Re-linking the same value to the same item returns 200."
        ),
        request=ExternalQrAssignSerializer,
        responses={
            201: ExternalQrAssignResultSerializer,
            200: ExternalQrAssignResultSerializer,
            409: OpenApiResponse(ExternalQrConflictSerializer, description="Code or item already linked."),
            **errors(400, 401, 403, 404),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = ExternalQrAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        makerspace = makerspace_for_action(request.user, rbac.Action.MANAGE_QR, data["makerspace_id"])
        require_module(makerspace, "qr_management")
        if request.user.access_status != User.AccessStatus.ACTIVE:
            raise PermissionDenied()
        value = clean_value(data["value"])
        if data.get("create_product") or data.get("create_asset"):
            require_module(makerspace, "staff_admin")
            require_action(request.user, rbac.Action.EDIT_INVENTORY, makerspace.id)
        if data.get("asset_id") or data.get("create_asset"):
            require_module(makerspace, "asset_units")  # unit labels are an asset_units surface
        with transaction.atomic():
            if data.get("create_product"):
                target_type, target = QrCode.TargetType.PRODUCT, _create_product(request, makerspace, data["create_product"])
            elif data.get("create_asset"):
                target_type, target = QrCode.TargetType.ASSET, _create_asset(request.user, makerspace, data["create_asset"])
            else:
                target_type, target = target_for(makerspace, product_id=data.get("product_id"), asset_id=data.get("asset_id"))
            qr, created = assign_external_qr(request.user, makerspace, value, target_type, target, source="scanner")
        return Response(
            {"qr": QrCodeSerializer(qr).data, "target": qr_target_payload(qr), "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


def _create_product(request, makerspace, fields):
    from apps.admin_api.serializers_inventory import InventoryProductAdminCreateSerializer
    from apps.admin_api.views_inventory_products import (
        _assert_box_in_makerspace,
        _assert_category_in_makerspace,
    )

    serializer = InventoryProductAdminCreateSerializer(data=fields, context={"request": request})
    if not serializer.is_valid():
        raise ValidationError({"create_product": serializer.errors})
    if serializer.validated_data.get("tracking_mode") == TrackingMode.INDIVIDUAL:
        raise ValidationError({"create_product": [gettext(
            "Create a quantity-tracked item here, or add a unit to an individual-tracked item.")]})
    _assert_box_in_makerspace(serializer.validated_data.get("box"), makerspace.id)
    _assert_category_in_makerspace(serializer.validated_data.get("category"), makerspace.id)
    product = serializer.save(makerspace_id=makerspace.id)
    audit.record(request.user, "inventory.created", makerspace=makerspace, target=product)
    return product


def _create_asset(actor, makerspace, fields):
    product = get_object_or_404(
        InventoryProduct.objects.select_for_update(), pk=fields["product_id"], makerspace=makerspace,
    )
    if product.tracking_mode != TrackingMode.INDIVIDUAL:
        raise ValidationError({"create_asset": [gettext("Units can only be added to individual-tracked items.")]})
    limits.check_quota(makerspace, "assets", adding=1)
    try:
        with transaction.atomic():
            asset = InventoryAsset.objects.create(
                makerspace=makerspace, product=product, box=product.box,
                asset_tag=fields["asset_tag"].strip(), serial_number=fields.get("serial_number", ""),
            )
    except IntegrityError as exc:
        raise ValidationError({"create_asset": [gettext("An asset with that tag already exists.")]}) from exc
    availability.reconcile_individual_product_from_assets(product)
    audit.record(actor, "asset_units.generated", makerspace=makerspace, target=product, meta={"count": 1})
    return asset
