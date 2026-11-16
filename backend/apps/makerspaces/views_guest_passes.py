"""Decision 223: the guest's, the sponsoring member's and the public's guest-pass routes.

* Holder: `my passes`, accept the waiver, buy a day pass.
* Sponsor member: bring a guest, see my guests, revoke one.
* Public: the day-pass products on sale (anonymous read).

Every route answers 404 when `membership` or the relevant `membership.*` switch is off
(#95). The sponsor route deliberately answers the SAME 202 whether or not the e-mail has an
account, so it cannot be used to discover who has one; the outcome shows in "my guests".
"""
from django.utils.translation import gettext, gettext_lazy
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.account_kind_guards import require_member_account
from apps.accounts.models import User
from apps.accounts.schemas_self_service import ACCOUNT_ERRORS as ERRORS
from apps.makerspaces import guest_pass_day, guest_pass_issue, guest_pass_lifecycle
from apps.makerspaces.guest_pass_policy import GuestPassError
from apps.makerspaces.guest_pass_queries import visit_summary
from apps.makerspaces.membership_features import require_membership_feature
from apps.makerspaces.models import DayPassProduct, GuestPass
from apps.makerspaces.serializers_guest_passes import (
    HolderPassListSerializer, HolderPassSerializer, PublicDayPassSerializer, PurchaseResultSerializer,
    PurchaseSerializer, RevokeInputSerializer, SponsorGuestSerializer, SponsorInputSerializer,
    SponsorResultSerializer, WaiverAcceptSerializer,
)
from apps.makerspaces.servability import servable_queryset

MEMBER_TAG, PUBLIC_TAG = "Member guest passes", "Public guest passes"
_GENERIC = gettext_lazy("If that e-mail belongs to an account, the guest has been given a pass for today.")


def _space(user, makerspace_id, feature="guest_passes"):
    require_member_account(user)
    if not user.is_active or user.access_status != "active":
        raise PermissionDenied()
    space = get_object_or_404(servable_queryset(), pk=makerspace_id)
    return require_membership_feature(space, feature)


def _own_pass(user, space, pass_id):
    return get_object_or_404(GuestPass.objects.select_related("makerspace", "product", "sponsor"),
                             pk=pass_id, makerspace=space, holder=user)


class MyGuestPassesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[MEMBER_TAG], summary="Your guest passes at this space",
                   description="Your own passes (never anyone else's), what each allows, whether the waiver "
                               "is still to accept, and the 30-day visit count behind the join prompt. "
                               "Needs membership.guest_passes.",
                   responses={200: HolderPassListSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id)
        rows = GuestPass.objects.filter(makerspace=space, holder=request.user).select_related(
            "makerspace", "product", "sponsor")[:50]
        summary = visit_summary(request.user, space)
        return Response(HolderPassListSerializer({"passes": list(rows), **{
            key: summary[key] for key in ("visits_30d", "join_threshold", "should_prompt_join")}}).data)


class MyGuestPassWaiverView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[MEMBER_TAG], summary="Accept the current waiver on your pass",
                   description="Records acceptance of the active waiver. Needs `accepted: true`. Audited.",
                   request=WaiverAcceptSerializer, responses={200: HolderPassSerializer, **ERRORS})
    def post(self, request, makerspace_id, pass_id):
        space = _space(request.user, makerspace_id)
        WaiverAcceptSerializer(data=request.data).is_valid(raise_exception=True)
        row = guest_pass_lifecycle.stamp_waiver(request.user, _own_pass(request.user, space, pass_id))
        return Response(HolderPassSerializer(row).data)


class SponsoredGuestsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "member_card_resolve"  # m17: people lookups share the card-resolve budget

    @extend_schema(tags=[MEMBER_TAG], summary="Guests you brought",
                   description="Name, date, status and whether items are outstanding. Nothing else about "
                               "the guest. Needs membership.guest_passes.",
                   responses={200: SponsorGuestSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id)
        return Response(SponsorGuestSerializer(
            guest_pass_issue.sponsor_guests(request.user, space)[:100], many=True).data)

    @extend_schema(tags=[MEMBER_TAG], summary="Bring a guest",
                   description="You must be an active member of the required tenure, checked in on site when "
                               "the space asks for it, and within the space's guest limit. The guest needs an "
                               "account. Always answers 202 with the same text whether or not the e-mail has "
                               "an account.",
                   request=SponsorInputSerializer, responses={202: SponsorResultSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = _space(request.user, makerspace_id)
        data = SponsorInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        guest = User.objects.filter(email__iexact=data.validated_data["email"], account_kind="member",
                                    is_active=True, retired_at__isnull=True, merged_into__isnull=True).first()
        if guest is None:
            # Sponsor-side refusals (tenure, presence, limit) still surface first, so a member learns
            # why they cannot bring anyone; only the guest's existence stays hidden.
            _probe_sponsor(request.user, space)
        else:
            try:
                guest_pass_issue.issue_sponsored_pass(
                    request.user, space, guest, operation_id=data.validated_data.get("operation_id"))
            except GuestPassError as error:
                if error.error_code not in _GUEST_SIDE:
                    raise
        return Response({"detail": _GENERIC}, status=status.HTTP_202_ACCEPTED)


_GUEST_SIDE = {"guest_not_eligible", "already_member", "pass_exists_today", "visit_cap_reached"}


def _probe_sponsor(sponsor, space):
    """Run the sponsor-only checks without a guest, so an unknown e-mail refuses exactly as a known one would."""
    from django.utils import timezone

    from apps.makerspaces.guest_pass_issue import _concurrent_guests, _sponsor_membership, _sponsor_present
    from apps.makerspaces.guest_pass_policy import policy_for
    policy = policy_for(space)
    _sponsor_membership(sponsor, space, policy, timezone.now())
    if policy.sponsor_must_be_present and not _sponsor_present(sponsor, space):
        raise GuestPassError("sponsor_presence_required", gettext("Check in at the space before bringing a guest."))
    if _concurrent_guests(sponsor, space, timezone.now()) >= policy.max_concurrent_guests_per_sponsor:
        raise GuestPassError("sponsor_limit", gettext("You already have the maximum number of guests."))


class SponsoredGuestRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[MEMBER_TAG], summary="Withdraw a guest's pass",
                   description="Only the sponsor of that pass. Needs membership.guest_passes.",
                   request=RevokeInputSerializer, responses={200: SponsorGuestSerializer, **ERRORS})
    def post(self, request, makerspace_id, pass_id):
        space = _space(request.user, makerspace_id)
        row = get_object_or_404(GuestPass.objects.select_related("holder"), pk=pass_id, makerspace=space,
                                sponsor=request.user)
        data = RevokeInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(SponsorGuestSerializer(
            guest_pass_lifecycle.revoke_pass(request.user, row, data.validated_data["reason"])).data)


class MemberDayPassListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[MEMBER_TAG], summary="Day passes you can buy here",
                   responses={200: PublicDayPassSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id, "day_passes")
        return Response(PublicDayPassSerializer(guest_pass_day.public_products(space), many=True).data)


class DayPassPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[MEMBER_TAG], summary="Buy a day pass",
                   description="Issues the pass for today or a later local day. A priced pass records the "
                               "amount owed first; it unlocks once the charge is paid or waived (online when "
                               "online payments are on, otherwise at the desk). Needs membership.day_passes.",
                   request=PurchaseSerializer, responses={201: PurchaseResultSerializer, **ERRORS})
    def post(self, request, makerspace_id, product_id):
        space = _space(request.user, makerspace_id, "day_passes")
        data = PurchaseSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        product = get_object_or_404(DayPassProduct, pk=product_id, makerspace=space, is_public=True)
        row, payment = guest_pass_day.sell_day_pass(
            request.user, space, request.user, product, day=data.validated_data.get("day"),
            operation_id=data.validated_data.get("operation_id"))
        return Response(PurchaseResultSerializer({
            "pass_id": row.pk, "status": row.status, "payment_id": payment.pk if payment else None,
            "payment_status": payment.status if payment else None, "amount": str(product.amount),
            "currency": payment.currency if payment else product.currency}).data, status=status.HTTP_201_CREATED)


class PublicDayPassListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=[PUBLIC_TAG], summary="Day passes on sale at a space",
                   description="Name and price only. 404 when guest passes or day passes are off.",
                   responses={200: PublicDayPassSerializer(many=True),
                              404: OpenApiResponse(description="Unknown space, or the feature is off.")})
    def get(self, request, makerspace_slug):
        space = get_object_or_404(servable_queryset(), slug=makerspace_slug)
        require_membership_feature(space, "guest_passes")
        require_membership_feature(space, "day_passes")
        return Response(PublicDayPassSerializer(guest_pass_day.public_products(space), many=True).data)

