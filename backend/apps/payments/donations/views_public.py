"""The public donation page, giving, pledging and the sponsor wall (#128 C-14).

Anyone may give: a signed-in person as themselves, a guest with name, email and the emailed
code. Each switch off answers 404 `feature_disabled`. Nothing here returns another person's
details, a hidden count or a PAN.
"""

from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.platform import feature_enabled
from apps.tenant_migration.gate_runtime import tenant_write

from . import serializers_public as s
from .gates import PLEDGES, SPONSORS, public_space, require_feature, tax_key
from .identity import PLEDGE_SALT, STATUS_SALT, donor_for, link_token, send_code
from .models import DonationCampaign, DonationSettings

ERRORS = {400: OpenApiResponse(ErrorSerializer), 404: OpenApiResponse(ErrorSerializer),
          429: OpenApiResponse(ErrorSerializer)}


class _Read:
    """Public reads share the platform's public-read budget (ClientTierRateThrottle)."""

    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"


class _Give:
    """Giving shares the account-less submission budget (`public_request_submit`)."""

    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_request_submit"


def open_campaigns(space):
    now = timezone.now()
    return DonationCampaign.objects.filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now), Q(ends_at__isnull=True) | Q(ends_at__gt=now),
        makerspace=space, is_active=True, is_public=True)


def raised(campaign):
    from .models import Donation

    total = Donation.objects.filter(campaign=campaign, status=Donation.Status.PAID).aggregate(t=Sum("amount"))["t"]
    return total or Decimal("0.00")


class DonationPageView(_Read, APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Donations"], summary="The space's donation page", auth=[],
                   description="Public. 404 `feature_disabled` while `finance.donations` is off.",
                   responses={200: s.DonationPageSerializer, **ERRORS})
    def get(self, request, makerspace_slug):
        from apps.payments.availability import online_payments_enabled

        from .services import space_currency
        from .tax_receipts import registration_live

        space = public_space(makerspace_slug)
        settings = DonationSettings.for_makerspace(space)
        tax = feature_enabled(space, "finance.tax_exempt_receipts") and registration_live(
            settings, timezone.localdate())
        campaigns = [{
            "id": row.pk, "kind": row.kind, "name": row.name, "slug": row.slug, "description": row.description,
            "goal_amount": row.goal_amount, "raised_amount": raised(row), "currency": row.currency,
            "starts_at": row.starts_at, "ends_at": row.ends_at} for row in open_campaigns(space)[:50]]
        return Response(s.DonationPageSerializer({
            "makerspace": space.name, "intro": settings.page_intro, "currency": space_currency(space),
            "minimum_amount": settings.minimum_amount,
            "suggested_amounts": [str(value) for value in (settings.suggested_amounts or [])][:8],
            "campaigns": campaigns, "online_available": online_payments_enabled(space, "donations"),
            "recurring_available": feature_enabled(space, PLEDGES), "tax_receipts_available": bool(tax),
            "tax_registration_number": settings.tax_exempt_registration_number if tax else "",
            "guest_allowed": True}).data)


class DonationEmailCodeView(_Give, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Donations"], summary="Email a one-time code to a guest giver", auth=[],
                   request=s.EmailCodeSerializer, responses={202: None, **ERRORS})
    def post(self, request, makerspace_slug):
        space = public_space(makerspace_slug)
        payload = s.EmailCodeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with tenant_write(space.pk):
            send_code(space, payload.validated_data["donor_email"])
        return Response(status=202)


class DonationCreateView(_Give, APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Donations"], summary="Give to the space (one-off)",
                   description="Signed in, the gift is yours; otherwise send donor_name, donor_email and the "
                               "email_code. Returns the hosted checkout URL when online payment is on, else the "
                               "offline instructions. 400 `donor_identity_required`, `amount_below_minimum`, "
                               "`campaign_closed`, `tax_receipts_unavailable`, `pan_invalid`. Audited "
                               "`donation.created`.",
                   request=s.DonationCreateSerializer, responses={201: s.GiftStatusSerializer, **ERRORS})
    def post(self, request, makerspace_slug):
        from .services import checkout_url, clean_amount, create_gift, open_campaign
        from .tax_receipts import clean_request

        space = public_space(makerspace_slug)
        payload = s.DonationCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        amount = clean_amount(space, data["amount"])
        campaign = open_campaign(space, data["campaign"])
        tax = clean_request(space, data)
        # Outside any transaction: a wrong code must burn its attempt even though the gift fails.
        donor = donor_for(request, space, data)
        with tax_key(space, tax), tenant_write(space.pk):
            donation, payment = create_gift(space, donor, amount=amount, campaign=campaign, note=data["note"],
                                            tax=tax)
        # The gift is committed first: a provider failure never loses it (the debt stays payable).
        with tenant_write(space.pk):
            checkout = checkout_url(payment)
        token = link_token(donation, "access_secret", STATUS_SALT) if donor.is_guest else ""
        return Response(s.GiftStatusSerializer(s.gift_status(donation, token=token, checkout=checkout)).data,
                        status=201)


class PledgeCreateView(_Give, APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Donations"], summary="Pledge a gift every period",
                   description="Needs `finance.recurring_donations`. Each period raises one charge the giver pays; "
                               "no card is stored. Guests get a signed manage link. Audited `pledge.created`.",
                   request=s.PledgeCreateSerializer, responses={201: s.PledgeStatusSerializer, **ERRORS})
    def post(self, request, makerspace_slug):
        from .pledges import create_pledge
        from .serializers_staff import pledge_status
        from .services import clean_amount, open_campaign
        from .tax_receipts import clean_request

        space = require_feature(public_space(makerspace_slug), PLEDGES)
        payload = s.PledgeCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        amount = clean_amount(space, data["amount"])
        campaign = open_campaign(space, data["campaign"])
        tax = clean_request(space, data)
        donor = donor_for(request, space, data)  # outside any transaction, like giving
        with tax_key(space, tax), tenant_write(space.pk):
            pledge = create_pledge(space, donor, amount=amount, interval=data["interval"],
                                   starts_on=data["starts_on"], campaign=campaign, tax=tax)
        token = link_token(pledge, "manage_secret", PLEDGE_SALT) if donor.is_guest else ""
        return Response(s.PledgeStatusSerializer(pledge_status(pledge, token=token)).data, status=201)


class SponsorWallView(_Read, APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Donations"], summary="The space's public sponsor wall", auth=[],
                   description="Public fields only (name, tier, logo, website, blurb). 404 while "
                               "`finance.sponsors` is off.", responses={200: s.SponsorWallSerializer, **ERRORS})
    def get(self, request, makerspace_slug):
        from .wall import wall

        space = public_space(makerspace_slug, SPONSORS)
        return Response({"results": wall(space)})


class EventSponsorWallView(_Read, APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Donations"], summary="Sponsors linked to one public event", auth=[],
                   description="The space sponsors linked to this event's own sponsors, public fields only. 404 for "
                               "an event that is not public and live, or while `finance.sponsors` is off.",
                   responses={200: s.SponsorWallSerializer, **ERRORS})
    def get(self, request, makerspace_slug, public_token):
        from apps.events.website_visibility import resolve

        from .wall import event_wall

        event = resolve(makerspace_slug, public_token)
        require_feature(event.makerspace, SPONSORS)
        return Response({"results": event_wall(event)})

