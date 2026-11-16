"""Allowlisted own borrowing history, extending the retained public-status projection."""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .serializers import PublicRequestItemStatusSerializer, PublicRequestStatusSerializer


class OwnBorrowingItemSerializer(PublicRequestItemStatusSerializer):
    accepted_quantity = serializers.IntegerField(read_only=True)
    issued_quantity = serializers.IntegerField(read_only=True)
    returned_quantity = serializers.IntegerField(read_only=True)
    damaged_quantity = serializers.IntegerField(read_only=True)
    missing_quantity = serializers.IntegerField(read_only=True)
    needs_fix_quantity = serializers.IntegerField(read_only=True)


class OwnReturnDateSerializer(serializers.Serializer):
    returned_at = serializers.DateTimeField(source="created_at", read_only=True)


class OwnBorrowingHistorySerializer(PublicRequestStatusSerializer):
    id = serializers.IntegerField(read_only=True)
    issued_at = serializers.DateTimeField(read_only=True, allow_null=True)
    return_due_at = serializers.DateTimeField(read_only=True, allow_null=True)
    closed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    items = OwnBorrowingItemSerializer(many=True, read_only=True)
    returns = OwnReturnDateSerializer(source="returnevent_set", many=True, read_only=True)
    source = serializers.SerializerMethodField()
    checked_out_at = serializers.SerializerMethodField()
    returned_at = serializers.SerializerMethodField()
    can_renew = serializers.SerializerMethodField(
        help_text="Whether the caller may renew this loan now (same check the renewal action runs).")
    renewal_refusal = serializers.SerializerMethodField(
        help_text="Refusal code when `can_renew` is false (for example `renewals_off`, `self_renewal_off`, `renewal_limit`).")

    renewals_left = serializers.SerializerMethodField(
        help_text="Renewals this loan may still take (policy cap minus renewals used); null when renewals are off.")

    def _resolver(self, row):
        resolvers = self.context.setdefault("renewal_resolvers", {})
        if row.makerspace_id not in resolvers:
            from .renewal_state import RenewalStateResolver
            resolvers[row.makerspace_id] = RenewalStateResolver(row.makerspace, self.context["request"].user)
        return resolvers[row.makerspace_id]

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_renewals_left(self, row) -> int | None:
        return self._resolver(row).renewals_left(row)

    def _renewal(self, row):
        cache = self.context.setdefault("renewal_state", {})
        if row.pk not in cache:
            cache[row.pk] = self._resolver(row).state(row)
        return cache[row.pk]

    @extend_schema_field(serializers.BooleanField())
    def get_can_renew(self, row) -> bool:
        return self._renewal(row)[0]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_renewal_refusal(self, row) -> str | None:
        return self._renewal(row)[1]

    def get_source(self, row) -> str:
        loan = getattr(row, "public_tool_loan", None)
        return loan.source if loan else "reviewed_request"

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_checked_out_at(self, row) -> str | None:
        loan = getattr(row, "public_tool_loan", None)
        return loan.checked_out_at.isoformat() if loan else None

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_returned_at(self, row) -> str | None:
        loan = getattr(row, "public_tool_loan", None)
        return loan.returned_at.isoformat() if loan and loan.returned_at else None
