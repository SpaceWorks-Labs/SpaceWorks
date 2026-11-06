"""Shared projection of valid membership role sets for staff and community lists."""

from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiResponse, extend_schema_field
from rest_framework import serializers

from apps.accounts.rbac_roles import membership_roles


ROLE_SET_VALIDATION_ERROR = OpenApiResponse(
    response={"type": "object", "additionalProperties": {}},
    description=("Field validation errors. Provide exactly one of role_id or role_ids; "
                 "the set must be nonempty, and Space Manager and Member are exclusive."),
)


class RoleSetInputSerializer(serializers.Serializer):
    role_id = serializers.IntegerField(required=False, help_text="Single-role set; omit role_ids.")
    role_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=False,
        help_text="Complete role set. Space Manager and Member must each be assigned alone.",
    )

    def validate(self, attrs):
        if ("role_id" in attrs) == ("role_ids" in attrs):
            raise serializers.ValidationError(gettext("Provide exactly one of role_id or role_ids."))
        if "role_ids" in attrs:
            attrs["role_ids"] = list(dict.fromkeys(attrs["role_ids"]))
        return attrs


def resolve_role_set(makerspace, data):
    """Keep unknown and foreign role IDs indistinguishable (404)."""
    from django.http import Http404
    from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
    from apps.makerspaces.role_membership_writes import validated_roles

    ids = data["role_ids"] if "role_ids" in data else [data["role_id"]]
    rows = list(MakerspaceRole.objects.filter(makerspace=makerspace, pk__in=ids))
    if len(rows) != len(set(ids)):
        raise Http404
    return validated_roles(MakerspaceMembership(makerspace=makerspace), rows)


class MembershipRoleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()


class MembershipRoleSetMixin:
    @extend_schema_field(serializers.ListField(child=serializers.IntegerField()))
    def get_role_ids(self, obj):
        return [role.pk for role in membership_roles(obj)]

    @extend_schema_field(MembershipRoleSerializer(many=True))
    def get_roles(self, obj):
        return MembershipRoleSerializer(membership_roles(obj), many=True).data
