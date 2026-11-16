"""Parity O-B1: request and response shapes of the member-unit staff routes (all documented in OpenAPI)."""
from rest_framework import serializers


class MemberUnitSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    parent_id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    slug = serializers.CharField()
    code = serializers.CharField(help_text="1 to 6 capital letters or digits, unique in the space.")
    level = serializers.IntegerField(help_text="0 for a top-level unit.")
    level_name = serializers.CharField(help_text="The space's name for this level, empty when unnamed.")
    path = serializers.CharField(help_text='Materialised code path, e.g. "/NORTH/KOCHI/". A subtree is every path with this prefix.')
    sort_order = serializers.IntegerField()
    archived = serializers.BooleanField()
    has_payment_instructions = serializers.BooleanField()


class MemberUnitDetailSerializer(MemberUnitSerializer):
    payment_instructions = serializers.CharField(help_text="The unit's own offline payment instructions.")
    effective_payment_instructions = serializers.CharField(
        help_text="Its own, else the nearest ancestor's. Empty when none is set.")
    effective_instructions_unit_id = serializers.IntegerField(allow_null=True)


class LevelTemplateSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    levels = serializers.ListField(child=serializers.CharField())


class MemberUnitListSerializer(serializers.Serializer):
    levels = serializers.ListField(child=serializers.CharField(), help_text="Names of levels 0..3, in order.")
    templates = LevelTemplateSerializer(many=True)
    units = MemberUnitSerializer(many=True)
    limit = serializers.IntegerField(allow_null=True, help_text="`member_units` allowance, null when unlimited.")
    used = serializers.IntegerField(help_text="Active (non-archived) units.")
    scoped = serializers.BooleanField(help_text="True when the list is narrowed to the caller's own unit subtree.")


class MemberUnitCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    code = serializers.CharField(max_length=6, required=False, allow_blank=True)
    payment_instructions = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    sort_order = serializers.IntegerField(required=False, min_value=0, max_value=100000)


class MemberUnitUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, required=False)
    code = serializers.CharField(max_length=6, required=False)
    payment_instructions = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    sort_order = serializers.IntegerField(required=False, min_value=0, max_value=100000)


class MemberUnitMoveSerializer(serializers.Serializer):
    parent_id = serializers.IntegerField(allow_null=True, help_text="The new parent; null makes it a top-level unit.")


class MemberUnitLevelsSerializer(serializers.Serializer):
    levels = serializers.ListField(child=serializers.CharField(max_length=40), max_length=4, allow_empty=True)


class UnitAssignmentSerializer(serializers.Serializer):
    unit_id = serializers.IntegerField(allow_null=True, help_text="Null removes the assignment.")


class UnitAssignmentResultSerializer(serializers.Serializer):
    membership_id = serializers.IntegerField()
    unit = MemberUnitSerializer(allow_null=True)


class PlanUnitsSerializer(serializers.Serializer):
    unit_ids = serializers.ListField(child=serializers.IntegerField(), max_length=500,
                                     help_text="Empty means the plan is offered in every unit.")


class MemberImportReviewSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="The ImportedMember id.")
    unit_id = serializers.IntegerField()
    review_status = serializers.CharField()
    row_status = serializers.CharField()
    name = serializers.CharField()
    email = serializers.CharField()
    created_at = serializers.DateTimeField()


class ReviewDecisionSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="The ImportedMember id.")
    review_status = serializers.CharField()
