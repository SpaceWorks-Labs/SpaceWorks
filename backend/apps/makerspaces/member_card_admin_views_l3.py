"""Release 2 L3 staff member-card routes: settings, design approval, single download,
email, "photo needs update". Authority by ACTION and every query scoped through rbac;
settings are written through the L17 settings authority (Space Manager or a grant).
"""
from django.utils.translation import gettext
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.audit import services as audit
from apps.openapi_errors import errors
from apps.card_designs.serializers_openapi import CreatedNoteSerializer, PresenceCheckInResultSerializer, QueuedSerializer
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace, MemberCard, MemberCardSettings

TAGS = ["Admin memberships"]
SETTING_KEYS = {"auto_issue": "member_cards.auto_issue", "email_on_issue": "member_cards.email_on_issue",
                "public_verify": "member_cards.public_verify", "verify_show_plan": "member_cards.verify_show_plan"}


class MemberCardSettingsSerializer(serializers.Serializer):
    auto_issue = serializers.BooleanField(required=False)
    email_on_issue = serializers.BooleanField(required=False)
    public_verify = serializers.BooleanField(required=False)
    verify_show_plan = serializers.BooleanField(required=False)
    design_approval_required = serializers.BooleanField(required=False)
    email_available = serializers.BooleanField(read_only=True)
    photo_cleanup_available = serializers.BooleanField(read_only=True)
    wallet_platforms = serializers.ListField(child=serializers.CharField(), read_only=True)


class CardNoteSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True)


def _space(actor, makerspace_id, action):
    space = get_object_or_404(rbac.scope_by_action(actor, action, Makerspace.objects.all(), field="id"), pk=makerspace_id)
    require_module(space, "membership")
    return space


def card_settings(space):
    row, _ = MemberCardSettings.objects.get_or_create(makerspace=space)
    return row


def _payload(space):
    from apps.card_designs import segmentation
    from apps.card_designs.approval import DEFAULTS
    from apps.card_designs.email import blocked
    from apps.card_designs.models import CardApprovalSetting
    from apps.card_designs.wallet.credentials import configured_platforms
    row = card_settings(space)
    approval = CardApprovalSetting.objects.filter(makerspace=space, group="membership", organization__isnull=True,
                                                  programme__isnull=True, event__isnull=True).first()
    return {**{name: getattr(row, name) for name in SETTING_KEYS},
            "design_approval_required": approval.required if approval else DEFAULTS["membership"],
            "email_available": not blocked(space), "photo_cleanup_available": segmentation.available(),
            "wallet_platforms": list(configured_platforms())}


class MemberCardSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Read member-card settings", request=None,
                   responses={200: MemberCardSettingsSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_id):
        return Response(_payload(_space(request.user, makerspace_id, rbac.Action.SCAN_MEMBER_CARDS)))

    @extend_schema(tags=TAGS, summary="Change member-card settings (Space Manager or a membership settings grant)",
                   request=MemberCardSettingsSerializer, responses={200: MemberCardSettingsSerializer, **errors(400, 401, 403, 404)})
    def put(self, request, makerspace_id):
        from apps.card_designs.approval import set_level
        from apps.makerspaces.settings_authority import assert_setting_write, record_change
        space = _space(request.user, makerspace_id, rbac.Action.MANAGE_MEMBER_CARDS)
        data = MemberCardSettingsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = card_settings(space)
        before = _payload(space)
        for name, key in SETTING_KEYS.items():
            if name in data.validated_data and data.validated_data[name] != getattr(row, name):
                decision = assert_setting_write(request.user, space, "membership", key)
                setattr(row, name, data.validated_data[name])
                record_change(request.user, space, "membership", key, before[name], data.validated_data[name], decision)
        row.save()
        wanted = data.validated_data.get("design_approval_required")
        if wanted is not None and wanted != before["design_approval_required"]:
            decision = assert_setting_write(request.user, space, "membership", "card_designs.approval")
            set_level(request.user, space, "membership", wanted)
            record_change(request.user, space, "membership", "card_designs.approval", before["design_approval_required"],
                          wanted, decision)
        audit.record(request.user, "member_card.settings_updated", makerspace=space, target=space, meta={})
        return Response(_payload(space))


def _card(actor, pk, action=rbac.Action.MANAGE_MEMBER_CARDS):
    card = get_object_or_404(rbac.scope_by_action(actor, action, MemberCard.objects.select_related(
        "makerspace", "membership__user", "membership__assigned_role")), pk=pk)
    require_module(card.makerspace, "membership")
    return card


class MemberCardDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Download one member card (PDF, or PNG of one side at 300 dpi)", request=None,
                   parameters=[OpenApiParameter("format", str, enum=["pdf", "png"]),
                               OpenApiParameter("side", str, enum=["front", "back"])],
                   responses={(200, "application/pdf"): OpenApiTypes.BINARY, (200, "image/png"): OpenApiTypes.BINARY,
                              **errors(400, 401, 403, 404)})
    def get(self, request, pk):
        from apps.card_designs.cards import render
        from apps.card_designs.downloads import record_download
        card = _card(request.user, pk)
        if not card.is_active:
            raise PermissionDenied(gettext("A revoked card cannot be downloaded."))
        fmt, side = request.query_params.get("format", "pdf"), request.query_params.get("side", "front")
        data, content_type, filename = render("member_card", card, fmt=fmt, side=side)
        record_download(request.user, "member_card", card, fmt, side)
        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class MemberCardEmailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Email this card to its holder (PDF attached)", request=None,
                   responses={202: QueuedSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        from apps.card_designs.email import blocked, send_card_email
        card = _card(request.user, pk)
        if blocked(card.makerspace):
            from apps.makerspaces.guards import module_off
            raise module_off("email", "Email is turned off for this space.")
        if not send_card_email("member_card", card, actor=request.user, explicit=True):
            raise ValidationError({"detail": gettext("This card was emailed in the last 10 minutes, the daily limit was "
                                             "reached, or the holder has no email address.")})
        return Response({"queued": True}, status=202)


class MemberCardPhotoRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Ask the holder for a new photo (the card stays valid)",
                   request=CardNoteSerializer, responses={201: CreatedNoteSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        from apps.card_designs.photos import request_update
        card = _card(request.user, pk)
        data = CardNoteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = request_update(request.user, "member_card", card, data.validated_data.get("reason", ""))
        return Response({"id": row.pk, "created_at": row.created_at}, status=201)


class CardScanSerializer(serializers.Serializer):
    payload = serializers.CharField(max_length=300)
    duration_minutes = serializers.IntegerField(min_value=15, max_value=480)


class MemberCardPresenceView(APIView):
    """A staffed station records space presence from a member-card scan (#132, Q-I10).

    The scan only identifies the person for the staff member, who is the actor; it never
    signs the member in. Needs card-scan AND presence-staff authority in this space.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Check a member in at the space by scanning their card",
                   request=CardScanSerializer, responses={201: PresenceCheckInResultSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id):
        from django.contrib.auth import get_user_model
        from django.http import Http404
        from apps.card_designs.scan import person_for
        from apps.separability.tombstones import app_is_tombstoned
        if app_is_tombstoned("presence"):
            raise Http404
        from apps.presence.services import staff_check_in
        space = _space(request.user, makerspace_id, rbac.Action.SCAN_MEMBER_CARDS)
        data = CardScanSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        account_id, card = person_for(space, data.validated_data["payload"], actor=request.user)
        if account_id is None:
            raise Http404
        account = get_user_model().objects.get(pk=account_id)
        session = staff_check_in(request.user, account, space, data.validated_data["duration_minutes"])
        audit.record(request.user, "card.scanned_for_checkin", makerspace=space, target=card,
                     meta={"place": "presence", "session_id": session.pk})
        return Response({"session_id": session.pk, "account_id": account_id}, status=201)
