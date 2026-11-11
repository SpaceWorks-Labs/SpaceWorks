"""Decision 248: bulk staff invitations -- many email invitations to one makerspace, all or nothing.

Each row runs the SAME `issue()` service as the single invitation route (same authority, role and machine-scope
checks, one `staff_invitation.sent` audit row each) inside ONE transaction, so a refusal on any row rolls the
earlier invitations back and names the failing address index. Delivery runs after commit and never undoes a row.
At most 50 invitations per call; addresses must be unique within the call.
"""

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from apps.accounts.services_staff_invitations import issue
from apps.accounts.staff_invitation_delivery import deliver
from apps.admin_api.bulk_decisions import ERRORS, MAX_IDS, BulkFailed
from apps.admin_api.views_staff_roles import TAGS, StaffRoleBase, _no_store


class StaffInviteItemSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    roles = serializers.ListField(child=serializers.CharField(), allow_empty=False, max_length=8)
    machine_type_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), default=list)
    machine_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), default=list,
                                        help_text="Individual machines, unioned with the types.")
    expires_in_days = serializers.IntegerField(min_value=1, max_value=30, default=7)


class StaffInviteBulkSerializer(serializers.Serializer):
    invites = StaffInviteItemSerializer(many=True, allow_empty=False, max_length=MAX_IDS)

    def validate_invites(self, value):
        emails = [row["email"].strip().lower() for row in value]
        if len(emails) != len(set(emails)):
            raise serializers.ValidationError("Addresses must be unique within one call.")
        return value


class StaffInviteBulkResultSerializer(serializers.Serializer):
    invited = serializers.IntegerField()
    invitation_ids = serializers.ListField(child=serializers.IntegerField())
    delivery = serializers.ListField(child=serializers.CharField(allow_null=True))


class StaffRoleBulkInviteView(StaffRoleBase):
    @extend_schema(tags=TAGS, summary="Invite many people by email (all or nothing, up to 50)",
                   description="Same authority as the single invitation route. A 409 `bulk_failed` carries "
                               "`failed_id` = the zero-based index of the invitation that was refused; nothing "
                               "was created. Only the superadmin may include the Space Manager role.",
                   request=StaffInviteBulkSerializer, responses={201: StaffInviteBulkResultSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        data = StaffInviteBulkSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        issued = []
        with transaction.atomic():
            for index, values in enumerate(data.validated_data["invites"]):
                try:
                    with transaction.atomic():
                        issued.append(issue(request.user, makerspace_id, email=values["email"], roles=values["roles"],
                                            machine_type_ids=values["machine_type_ids"],
                                            machine_ids=values["machine_ids"],
                                            expires_in_days=values["expires_in_days"]))
                except APIException as exc:
                    raise BulkFailed(index, exc) from exc
        delivery = [deliver(row, raw)["delivery_status"] for row, raw in issued]
        return _no_store(Response({"invited": len(issued), "invitation_ids": [row.pk for row, _ in issued],
                                   "delivery": delivery}, status=201))
