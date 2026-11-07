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
