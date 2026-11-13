"""Staff panel behind a scanned verify link (O-B4, parity C15).

`GET admin/card-verifications/<token>/staff` (authenticated). A staff member who scans a card's public
check link sees the member and the actions they may take next. Only when the actor holds
`SCAN_MEMBER_CARDS` in the card's space AND the member is inside the actor's scope; every other case is
the same uniform 404, so the public page never hints at membership elsewhere. The actions are links to
the existing service routes (renew -> extend, record payment, revoke card): no new mutation path.
A scan identifies, it never authenticates (INVARIANTS: member cards).
"""
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.audit import services as audit
from apps.makerspaces.platform import module_enabled
from apps.openapi_errors import errors

from .holders import registered
from .models import CardVerifyToken
from .tokens import SHAPE

TAGS = ["Card verification"]
AUDIT_WINDOW_SECONDS = 300


class StaffActionSerializer(serializers.Serializer):
    key = serializers.ChoiceField(choices=("renew", "record_payment", "revoke_card"))
    method = serializers.CharField()
    path = serializers.CharField(help_text="API route (relative to /api/v1/admin/) that performs the action.")


class StaffMemberSerializer(serializers.Serializer):
    name = serializers.CharField(allow_blank=True)
    number = serializers.CharField(allow_blank=True)
    plan = serializers.CharField(allow_blank=True)
    valid_until = serializers.CharField(allow_blank=True)


class VerifyStaffPanelSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    membership_id = serializers.IntegerField()
    member_url = serializers.CharField(help_text="Console path of the member in the register.")
    card_state = serializers.ChoiceField(choices=("valid", "expired", "revoked"))
    member = StaffMemberSerializer()
    actions = StaffActionSerializer(many=True)


def in_member_scope(actor, membership):
    """O-B1 unit-scoped staff: the member must also sit inside the actor's unit scope (for THIS action)."""
    from apps.makerspaces.member_unit_scope import member_in_scope
    return member_in_scope(actor, membership, rbac.Action.SCAN_MEMBER_CARDS)


def _panel(actor, token):
    if not isinstance(token, str) or not SHAPE.match(token):
        raise NotFound()
    row = CardVerifyToken.objects.filter(token=token, member_card__isnull=False).select_related(
        "member_card__membership", "makerspace").first()
    card = row.member_card if row else None
    membership = card.membership if card else None
    if (membership is None or not module_enabled(card.makerspace, "membership")
            or not rbac.can(actor, rbac.Action.SCAN_MEMBER_CARDS, card.makerspace_id)
            or not in_member_scope(actor, membership)):
        raise NotFound()
    spec = registered()["member_card"]
    standing = "revoked" if row.retired_at is not None else spec.standing(card)
    values = spec.snapshot(card)
    space_id, actions = card.makerspace_id, []
    if rbac.can(actor, rbac.Action.MANAGE_MEMBERS, space_id):
        actions.append({"key": "renew", "method": "POST", "path": f"memberships/{membership.pk}/extend"})
    if rbac.can(actor, rbac.Action.RECORD_PAYMENT, space_id):
        actions.append({"key": "record_payment", "method": "POST", "path": f"memberships/{membership.pk}/record"})
    if card.is_active and rbac.can(actor, rbac.Action.MANAGE_MEMBER_CARDS, space_id):
        actions.append({"key": "revoke_card", "method": "POST", "path": f"member-cards/{card.pk}/revoke"})
    if cache.add(f"card_staff_view:{actor.pk}:{card.pk}", 1, AUDIT_WINDOW_SECONDS):
        # Throttled: one row per actor and card per window; the token never enters the audit meta.
        audit.record(actor, "card_verification.staff_viewed", makerspace=card.makerspace, target=card,
                     meta={"card_id": card.pk, "state": standing})
    return {"makerspace_id": space_id, "membership_id": membership.pk,
            "member_url": f"/admin/members?id={membership.pk}", "card_state": standing,
            "member": {key: values.get(key, "") or "" for key in ("name", "number", "plan", "valid_until")},
            "actions": actions}


class CardVerificationStaffView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Staff panel for a scanned card check link",
                   description="Needs member-card scanning in the card's space and the member in the actor's scope; "
                               "otherwise a uniform 404. Actions point at the existing service routes.",
                   request=None, responses={200: VerifyStaffPanelSerializer, **errors(401, 404)})
    def get(self, request, token):
        return Response(_panel(request.user, token))
