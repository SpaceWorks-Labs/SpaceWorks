"""Staff donations: settings, campaigns, the gift list, desk gifts, cancellation and returns.

Finance staff or the Fundraising role (#100, decision 242(m)): reading needs `view_finance` or
`manage_donations`; recording, cancelling and opening a return case also need one of
`manage_donations`/`record_payment`; the page text and the non-profit profile are finance
settings, written through the settings authority (Space Manager only, never delegated).
"""

from django.utils.translation import gettext
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.tenant_migration.gate_runtime import tenant_write

from . import serializers_staff as s
from .gates import DONATIONS, PLEDGES, TAX, require_feature, scoped, staff_space, tax_key
from .models import Donation, DonationCampaign, DonationPledge, DonationSettings
from .serializers_public import PledgeActionSerializer

ERRORS = {400: OpenApiResponse(ErrorSerializer), 403: OpenApiResponse(ErrorSerializer),
          404: OpenApiResponse(ErrorSerializer), 409: OpenApiResponse(ErrorSerializer)}
TAG = ["Donations (staff)"]


def _text(value):
    return "" if value is None else str(value)


def payments_by_gift(rows):
    from apps.payments.models import Payment

    ids = [row.pk for row in rows]
    return {payment.subject_id: payment for payment in Payment.objects.filter(subject_type="donation",
                                                                               subject_id__in=ids)}


def claims_by_gift(payments):
    """Each gift's open "I've paid" claim, keyed by gift id (one query)."""
    from apps.payments.models import PaymentClaim

    by_payment = {payment.pk: gift_id for gift_id, payment in payments.items()}
    return {by_payment[claim.payment_id]: claim for claim in PaymentClaim.objects.filter(
        payment_id__in=list(by_payment), status__in=PaymentClaim.OPEN_STATUSES)}


def gift_or_404(request, makerspace_id, pk, *, record=False):
    staff_space(request.user, makerspace_id, DONATIONS, record=record)
    donation = scoped(request.user, Donation, makerspace_id).select_related("makerspace", "campaign").filter(
        pk=pk).first()
    if donation is None:
        raise NotFound(gettext("Donation not found."))
    return donation


class DonationSettingsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Donation page text and the non-profit profile",
                   responses={200: s.DonationSettingsSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, DONATIONS)
        return Response(s.DonationSettingsSerializer(DonationSettings.for_makerspace(space)).data)

    @extend_schema(tags=TAG, summary="Change donation settings (Space Manager only)",
                   description="Finance settings: Space Manager only, never delegated (`setting_not_delegated`). "
                               "Audited `settings.changed` per key.",
                   request=s.DonationSettingsSerializer, responses={200: s.DonationSettingsSerializer, **ERRORS})
    def put(self, request, makerspace_id):
        from apps.makerspaces.settings_authority import assert_setting_write, record_change

        space = staff_space(request.user, makerspace_id, DONATIONS)
        decision = assert_setting_write(request.user, space, "finance", "finance.donations")
        row = DonationSettings.for_makerspace(space)
        payload = s.DonationSettingsSerializer(row, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        before = s.DonationSettingsSerializer(row).data
        with tenant_write(space.pk):
            row = payload.save(makerspace=space, updated_by=request.user)
            after = s.DonationSettingsSerializer(row).data
            for key in payload.validated_data:
                record_change(request.user, space, "finance", f"donations.{key}", _text(before.get(key)),
                              _text(after.get(key)), decision)
        return Response(after)


class CampaignListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Campaigns and funds", responses={200: s.CampaignSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        staff_space(request.user, makerspace_id, DONATIONS)
        return Response(s.CampaignSerializer(scoped(request.user, DonationCampaign, makerspace_id), many=True).data)

    @extend_schema(tags=TAG, summary="Create a campaign or fund", description="Audited `donation.campaign_created`.",
                   request=s.CampaignSerializer, responses={201: s.CampaignSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        from .services import space_currency

        space = staff_space(request.user, makerspace_id, DONATIONS, record=True)
        payload = s.CampaignSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        from apps.managed_hosting.extra_quotas import check_extra_quota
        with tenant_write(space.pk):
            check_extra_quota(space, "donation_campaigns")  # decision 284: typed 409; gifts to existing ones never read it
            row = payload.save(makerspace=space, currency=space_currency(space), created_by=request.user)
            audit.record(request.user, "donation.campaign_created", makerspace=space, target=row,
                         meta={"campaign_id": row.pk, "kind": row.kind})
        return Response(s.CampaignSerializer(row).data, status=201)


class CampaignDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Change a campaign or fund", description="Audited `donation.campaign_updated`.",
                   request=s.CampaignSerializer, responses={200: s.CampaignSerializer, **ERRORS})
    def patch(self, request, makerspace_id, pk):
        space = staff_space(request.user, makerspace_id, DONATIONS, record=True)
        row = scoped(request.user, DonationCampaign, makerspace_id).filter(pk=pk).first()
        if row is None:
            raise NotFound(gettext("Campaign not found."))
        payload = s.CampaignSerializer(row, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        with tenant_write(space.pk):
            row = payload.save()
            audit.record(request.user, "donation.campaign_updated", makerspace=space, target=row,
                         meta={"campaign_id": row.pk, "fields": sorted(payload.validated_data)})
        return Response(s.CampaignSerializer(row).data)


class DonationListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Gifts received and pending",
                   parameters=[OpenApiParameter("status", str, required=False),
                               OpenApiParameter("campaign", int, required=False)],
                   responses={200: s.DonationSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        staff_space(request.user, makerspace_id, DONATIONS)
        rows = scoped(request.user, Donation, makerspace_id).select_related("campaign")
        if request.query_params.get("status"):
            rows = rows.filter(status=request.query_params["status"])
        if str(request.query_params.get("campaign") or "").isdigit():
            rows = rows.filter(campaign_id=int(request.query_params["campaign"]))
        rows = list(rows[:500])
        payments = payments_by_gift(rows)
        context = {"request": request, "payments": payments, "claims": claims_by_gift(payments)}
        return Response(s.DonationSerializer(rows, many=True, context=context).data)

    @extend_schema(tags=TAG, summary="Record a gift received in person",
                   description="Raises the gift's charge and settles it offline with the receipt in one go "
                               "(maker-checker applies). Audited `donation.created` and `payment.paid_offline`.",
                   request=s.DeskGiftSerializer, responses={201: s.DonationSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        from .identity import Donor
        from .services import clean_amount, open_campaign, record_desk_gift
        from .tax_receipts import clean_request

        space = staff_space(request.user, makerspace_id, DONATIONS, record=True)
        payload = s.DeskGiftSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        tax = clean_request(space, data)
        with tax_key(space, tax), tenant_write(space.pk):
            from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester

            donor = Donor(account=None, name=data["donor_name"].strip(), email=data["donor_email"].strip().lower(),
                          actor=get_or_create_anonymous_requester(space))
            donation = record_desk_gift(space, donor, actor=request.user, amount=clean_amount(space, data["amount"]),
                                        settlement=data["settlement"], campaign=open_campaign(
                                            space, data["campaign"], staff=True), note=data["note"],
                                        tax=tax, recognize=data["recognize_publicly"])
        context = {"request": request, "payments": payments_by_gift([donation])}
        return Response(s.DonationSerializer(donation, context=context).data, status=201)


class DonationActionView(APIView):
    """`cancel` a pending gift, or open a `return` case on a received one (staff decide it)."""

    permission_classes = [IsActiveStaff]
    action = "cancel"

    @extend_schema(tags=TAG, summary="Cancel a pending gift, or open a case to return a received one",
                   description="Return opens a refund case in area `donations`; nothing moves until staff approve "
                               "it in the refund-case queue (#59). Audited `donation.cancelled` / "
                               "`donation.return_case_opened`.",
                   request=s.NoteSerializer, responses={200: s.DonationSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        from .refunds import open_return_case
        from .services import cancel_gift
        from .tax_receipts import payment_for

        donation = gift_or_404(request, makerspace_id, pk, record=True)
        payload = s.NoteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with tenant_write(donation.makerspace_id):
            if self.action == "cancel":
                donation = cancel_gift(donation, actor=request.user, reason=payload.validated_data["reason"])
            else:
                open_return_case(payment_for(donation), actor=request.user, reason=payload.validated_data["reason"])
        context = {"request": request, "payments": payments_by_gift([donation])}
        return Response(s.DonationSerializer(donation, context=context).data)


class StaffTaxReceiptView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Download a gift's 80G receipt (PDF)",
                   description="The PAN is printed masked for a superadmin without a PII window.",
                   responses={(200, "application/pdf"): OpenApiResponse(OpenApiTypes.BINARY), **ERRORS})
    def get(self, request, makerspace_id, pk):
        from apps.accounts.pii_presentation import pii_visible

        from .tax_receipt_pdf import pdf_response

        donation = gift_or_404(request, makerspace_id, pk)
        require_feature(donation.makerspace, TAX)
        if not donation.tax_receipt:
            raise NotFound({"detail": gettext("No tax-exempt receipt was issued for this gift."), "code": "no_tax_receipt"})
        return pdf_response(donation, show_pan=pii_visible(request.user, donation.makerspace_id))


class PledgeListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Pledges", responses={200: s.PledgeSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        staff_space(request.user, makerspace_id, PLEDGES)
        rows = scoped(request.user, DonationPledge, makerspace_id).select_related("campaign")[:500]
        return Response(s.PledgeSerializer(rows, many=True, context={"request": request}).data)


class PledgeActionView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Pause, resume or cancel a pledge",
                   description="Audited `pledge.paused|resumed|cancelled|updated`.",
                   request=PledgeActionSerializer, responses={200: s.PledgeSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        from .pledges import change_pledge

        staff_space(request.user, makerspace_id, PLEDGES, record=True)
        pledge = scoped(request.user, DonationPledge, makerspace_id).filter(pk=pk).first()
        if pledge is None:
            raise NotFound(gettext("Pledge not found."))
        payload = PledgeActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with tenant_write(pledge.makerspace_id):
            pledge = change_pledge(pledge, actor=request.user, action=data["action"], amount=data["amount"],
                                   interval=data["interval"])
        return Response(s.PledgeSerializer(pledge, context={"request": request}).data)
