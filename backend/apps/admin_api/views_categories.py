from django.utils.translation import gettext
from django.db import IntegrityError
from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.admin_api.serializers_inventory import CategoryAdminSerializer
from apps.audit import services as audit
from apps.inventory.models import Category
from apps.makerspaces.guards import require_module


@extend_schema(tags=["Admin inventory"], summary="List or create inventory categories")
class CategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = CategoryAdminSerializer
    permission_classes = [IsActiveStaff]

    def get_queryset(self):
        makerspace_id = self.kwargs["makerspace_id"]
        require_module(makerspace_id, "staff_admin")
        require_action(self.request.user, rbac.Action.VIEW_INVENTORY, makerspace_id)
        return (
            Category.objects.filter(makerspace_id=makerspace_id)
            .annotate(product_count=Count("products"))
            .order_by("display_order", "name")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["makerspace_id"] = self.kwargs["makerspace_id"]
        return context

    def perform_create(self, serializer):
        makerspace_id = self.kwargs["makerspace_id"]
        require_module(makerspace_id, "staff_admin")
        require_action(self.request.user, rbac.Action.EDIT_INVENTORY, makerspace_id)
        try:
            instance = serializer.save(makerspace_id=makerspace_id)
        except IntegrityError:
            raise ValidationError(
                {
                    "slug": gettext("A category with this slug already exists in this makerspace.")
                }
            )
        audit.record(
            self.request.user,
            "category.created",
            makerspace=instance.makerspace,
            target=instance,
        )


@extend_schema(
    tags=["Admin inventory"],
    summary="Retrieve, update, or delete inventory category",
)
class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CategoryAdminSerializer
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return rbac.scope_by_action(
            self.request.user,
            rbac.Action.VIEW_INVENTORY,
            Category.objects.select_related("makerspace").annotate(
                product_count=Count("products")
            ),
        )

    def get_object(self):
        category = super().get_object()
        require_module(category.makerspace_id, "staff_admin")
        return category

    def perform_update(self, serializer):
        require_action(
            self.request.user,
            rbac.Action.EDIT_INVENTORY,
            serializer.instance.makerspace_id,
        )
        try:
            instance = serializer.save()
        except IntegrityError:
            raise ValidationError(
                {
                    "slug": gettext("A category with this slug already exists in this makerspace.")
                }
            )
        audit.record(
            self.request.user,
            "category.updated",
            makerspace=instance.makerspace,
            target=instance,
        )

    def perform_destroy(self, instance):
        require_action(
            self.request.user,
            rbac.Action.EDIT_INVENTORY,
            instance.makerspace_id,
        )
        detached_product_count = instance.products.count()
        audit.record(
            self.request.user,
            "category.deleted",
            makerspace=instance.makerspace,
            target=instance,
            meta={"detached_product_count": detached_product_count},
        )
        instance.delete()
