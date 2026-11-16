from django.db.models import Count, F, Q
from apps.makerspaces.role_catalog import COMBINABLE_ROLE_SLUGS
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.makerspaces.models import MakerspaceRole


class RoleSerializer(serializers.ModelSerializer):
    makerspace_id = serializers.IntegerField(read_only=True)
    granted_actions = serializers.SerializerMethodField()
    combinable = serializers.SerializerMethodField()
    exclusive = serializers.SerializerMethodField()
    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = MakerspaceRole
        fields = (
            "id", "makerspace_id", "name", "slug", "granted_actions", "legacy_role",
            "is_default", "is_protected", "combinable", "exclusive", "member_count", "created_at", "updated_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_combinable(self, obj):
        return obj.slug in COMBINABLE_ROLE_SLUGS

    @extend_schema_field(serializers.BooleanField())
    def get_exclusive(self, obj):
        return obj.slug in {"space_manager", "member"}

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_granted_actions(self, obj):
        return sorted(obj.granted_actions) if isinstance(obj.granted_actions, list) else []


def role_queryset():
    # Count people once even if a corrupt redundant additional row names primary.
    primary = Count("memberships", distinct=True, filter=Q(
        memberships__makerspace_id=F("makerspace_id"),
    ))
    additional = Count("additional_memberships__membership", distinct=True, filter=(
        Q(slug__in=COMBINABLE_ROLE_SLUGS,
          additional_memberships__membership__makerspace_id=F("makerspace_id"),
          additional_memberships__membership__assigned_role__makerspace_id=F("makerspace_id"),
          additional_memberships__membership__assigned_role__slug__in=COMBINABLE_ROLE_SLUGS)
        & ~Q(additional_memberships__membership__assigned_role_id=F("pk"))
    ))
    return MakerspaceRole.objects.annotate(member_count=primary + additional)
