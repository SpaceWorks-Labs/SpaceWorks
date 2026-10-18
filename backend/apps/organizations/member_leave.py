"""Owner-self organization withdrawal, with a timestamp revision and durable replay."""

from datetime import UTC, datetime

from django.conf import settings
from django.db import models, transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication import require_recent_reauth
from apps.accounts.models import User
from apps.admin_api.permissions import active_user
from apps.audit.services import record
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations import governance
from apps.organizations.services_governance import assert_governor_remains


from .models_leave import OrganizationLeaveReceipt


def membership_version(row):
    # Avoid float timestamp rounding; revisions preserve exact database microseconds.
    delta = row.updated_at.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
    return ((delta.days * 86400 + delta.seconds) * 1_000_000) + delta.microseconds


def project_leave_state(organization, actor):
    """Ready-to-install owner-self projection; grants no membership-directory access."""
    if not active_user(actor) or actor.account_kind != "member":
        raise PermissionDenied()
    membership = get_object_or_404(OrganizationMembership, organization=organization, user=actor)
    is_governor = governance.MANAGE_ORGANIZATION_MEMBERS in governance.actions_for_membership(membership)
    has_successor = not is_governor or organization.memberships.filter(
        status="active", governance_actions__contains=[governance.MANAGE_ORGANIZATION_MEMBERS],
    ).exclude(pk=membership.pk).exists()
    return {"organization_id": organization.pk, "membership_version": membership_version(membership),
            "allowed_actions": ["leave"] if has_successor else [],
            "reason": None if has_successor else "sole_owner"}


class LeaveConflict(APIException):
    status_code = 409

    def __init__(self, code, detail):
        super().__init__({"code": code, "detail": detail})


@transaction.atomic
def leave_organization(*, request, organization_id, operation_id, expected_version):
    actor = request.user
    if not active_user(actor) or actor.account_kind != "member":
        raise PermissionDenied()
    require_recent_reauth(request)
    organization = get_object_or_404(Organization.objects.select_for_update(), pk=organization_id)
    request.user = actor = User.objects.select_for_update().get(pk=actor.pk)
    if not active_user(actor) or actor.account_kind != "member":
        raise PermissionDenied()
    # Recheck the proof under the same transaction as the authority withdrawal.
    require_recent_reauth(request)
    receipt = OrganizationLeaveReceipt.objects.filter(
        organization=organization, actor=actor, operation_id=operation_id).first()
    if receipt:
        if receipt.expected_version != expected_version:
            raise LeaveConflict("idempotency_conflict", "This operation ID was already used.")
        return {"organization_id": organization.pk, "state": "left", "allowed_actions": []}
    membership = get_object_or_404(
        OrganizationMembership.objects.select_for_update(), organization=organization, user=actor)
    if membership_version(membership) != expected_version:
        raise LeaveConflict("stale_version", "Your organization membership changed. Reload before leaving.")
    assert_governor_remains(organization, replaced_id=membership.pk, deleting=True)
    record(actor, "organization.member_left", target=organization,
           meta={"membership_id": membership.pk, "operation_id": str(operation_id)})
    membership.delete()
    OrganizationLeaveReceipt.objects.create(organization=organization, actor=actor,
                                           operation_id=operation_id, expected_version=expected_version)
    return {"organization_id": organization.pk, "state": "left", "allowed_actions": []}


class LeaveInput(serializers.Serializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=1)

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError("Unknown field.")
        return super().to_internal_value(data)


class LeaveOutput(serializers.Serializer):
    organization_id = serializers.IntegerField()
    state = serializers.ChoiceField(choices=("left",))
    allowed_actions = serializers.ListField(child=serializers.CharField())


class LeaveError(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()


class MemberOrganizationLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member organizations"], request=LeaveInput,
                   responses={200: LeaveOutput, **{code: LeaveError for code in (400, 401, 403, 404, 409, 429)}})
    def post(self, request, pk):
        payload = LeaveInput(data=request.data)
        payload.is_valid(raise_exception=True)
        result = leave_organization(request=request, organization_id=pk, **payload.validated_data)
        return Response(result, headers={"Cache-Control": "private, no-store"})
