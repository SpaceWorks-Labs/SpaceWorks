"""The Donations area's extra staff routes (decision 242(m)): donors, export, receipts, paid claims.

Same authority as every staff donations route (`gates.staff_space`): `manage_donations` (the
Fundraising role, the Space Manager) or `view_finance`; every write also needs
`manage_donations` or `record_payment`. Never an area manager's. Donor details are scoped PII:
a superadmin without a PII window reads them masked and cannot export them.
"""

from collections import defaultdict
from decimal import Decimal

from django.utils import timezone
from django.utils.translation import gettext
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.pii_presentation import MASK, pii_visible, require_pii_access
from apps.admin_api.permissions import IsActiveStaff
from apps.audit import services as audit
from apps.payments.serializers_l5 import StaffClaimSerializer
from apps.tenant_migration.gate_runtime import tenant_write

from .gates import DONATIONS, DonationRefused, scoped, staff_space
from .models import Donation
from .serializers_staff import DonationSerializer
from .views_staff import ERRORS, TAG, gift_or_404, payments_by_gift

EXPORT_FIELDS = ("id", "created_at", "paid_at", "status", "source", "amount", "currency", "campaign", "donor_name",
                 "donor_email", "guest", "recurring", "recognize_publicly", "tax_receipt_number", "payment_status")


class DonorSerializer(serializers.Serializer):
    key = serializers.CharField(help_text="`account:<id>` or `guest:<n>`; stable only within one response.")
    name = serializers.CharField(allow_blank=True)
    email = serializers.CharField(allow_blank=True)
    is_guest = serializers.BooleanField()
    gift_count = serializers.IntegerField()
    totals = serializers.DictField(child=serializers.CharField(), help_text="Received money per currency.")
    last_gift_at = serializers.DateTimeField(allow_null=True)
    recurring = serializers.BooleanField(help_text="Has an active pledge.")
    recognize_publicly = serializers.BooleanField(help_text="Chose to be named on a campaign page.")
    pii_masked = serializers.BooleanField(required=False)


class ClaimDecisionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=300, default="")


def donors(rows, active_pledgers, *, masked):
    groups = defaultdict(lambda: {"gifts": 0, "totals": defaultdict(Decimal), "last": None, "recognized": False})
    names = {}
    for gift in rows:
        key = f"account:{gift.donor_id}" if gift.donor_id else f"guest:{(gift.donor_email or '').lower()}"
        group = groups[key]
        names.setdefault(key, (gift.donor_name, gift.donor_email, gift.donor_id is None))
        if gift.status == Donation.Status.PAID:
            group["gifts"] += 1
            group["totals"][gift.currency] += gift.amount
            group["recognized"] = group["recognized"] or gift.recognize_publicly
        if group["last"] is None or gift.created_at > group["last"]:
            group["last"] = gift.created_at
    result = []
    for index, (key, group) in enumerate(sorted(groups.items(), key=lambda item: item[1]["last"], reverse=True)):
        name, email, guest = names[key]
        row = {"key": key if not guest else f"guest:{index}", "name": name, "email": email, "is_guest": guest,
               "gift_count": group["gifts"], "totals": {cur: str(total) for cur, total in group["totals"].items()},
               "last_gift_at": group["last"], "recognize_publicly": group["recognized"],
               "recurring": key in active_pledgers}
        if masked and (name or email):
            row.update(name=MASK if name else "", email=MASK if email else "", pii_masked=True)
        result.append(row)
    return result


class DonorListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Donors: who gave, how much and how often",
                   description="One row per signed-in giver (or guest email). Never a PAN or address. Masked for a "
                               "superadmin without a PII window.", responses={200: DonorSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        from .models import DonationPledge

        staff_space(request.user, makerspace_id, DONATIONS)
        rows = scoped(request.user, Donation, makerspace_id).exclude(status=Donation.Status.CANCELLED)[:5000]
        # Model rows, not values_list: a guest's email is scoped PII, decrypted on load.
        pledgers = {f"account:{row.donor_id}" if row.donor_id else f"guest:{(row.donor_email or '').lower()}"
                    for row in scoped(request.user, DonationPledge, makerspace_id).filter(status="active")[:5000]}
        masked = not pii_visible(request.user, makerspace_id)
        return Response(DonorSerializer(donors(rows, pledgers, masked=masked), many=True).data)


class DonationExportView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Download gifts as CSV",
                   description="Names and emails of givers, never a PAN or address. A superadmin needs an open PII "
                               "window (`pii_access_required`). Audited `donation.exported`.",
                   parameters=[OpenApiParameter("status", str, required=False),
                               OpenApiParameter("campaign", int, required=False)],
                   responses={(200, "text/csv"): OpenApiTypes.STR, **ERRORS})
    def get(self, request, makerspace_id):
        from apps.admin_api.exports import csv_response

        space = staff_space(request.user, makerspace_id, DONATIONS)
        require_pii_access(request.user, makerspace_id)
        rows = scoped(request.user, Donation, makerspace_id).select_related("campaign")
        status = request.query_params.get("status") or ""
        campaign = str(request.query_params.get("campaign") or "")
        rows = rows.filter(status=status) if status else rows
        rows = rows.filter(campaign_id=int(campaign)) if campaign.isdigit() else rows
        rows = list(rows[:20000])
        payments = payments_by_gift(rows)
        table = [EXPORT_FIELDS] + [(
            gift.pk, gift.created_at.isoformat(), gift.paid_at.isoformat() if gift.paid_at else "", gift.status,
            gift.source, str(gift.amount), gift.currency, gift.campaign.name if gift.campaign_id else "",
            gift.donor_name, gift.donor_email, gift.donor_id is None, gift.pledge_id is not None,
            gift.recognize_publicly, (gift.tax_receipt or {}).get("number", ""),
            getattr(payments.get(gift.pk), "status", "")) for gift in rows]
        audit.record(request.user, "donation.exported", makerspace=space, target=space, meta={
            "rows": len(rows), "status": status, "campaign_id": int(campaign) if campaign.isdigit() else None})
        return csv_response(table, f"donations-{space.slug}-{timezone.localdate().isoformat()}.csv")


class ReceiptReissueView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Send a received gift's receipt again",
                   description="Issues the tax receipt first when the giver asked for one, the space is a non-profit "
                               "and an exemption was live on the day the gift was received. 400 "
                               "`donation_not_received`. Audited `donation.receipt_reissued`.",
                   request=None, responses={200: DonationSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        from .notices import notify_receipt
        from .tax_receipts import freeze

        donation = gift_or_404(request, makerspace_id, pk, record=True)
        if donation.status != Donation.Status.PAID:
            raise DonationRefused(gettext("Only a received gift has a receipt."), "donation_not_received")
        with tenant_write(donation.makerspace_id):
            receipt = freeze(donation)
            audit.record(request.user, "donation.receipt_reissued", makerspace=donation.makerspace,
                         target=donation, meta={"donation_id": donation.pk, "tax_receipt": bool(receipt)})
        notify_receipt(donation, marker=timezone.now().isoformat())
        return Response(DonationSerializer(donation, context={"request": request,
                                                              "payments": payments_by_gift([donation])}).data)


class GiftClaimDecisionView(APIView):
    """Confirm or reject a giver's "I've paid" claim on one gift (decision 242(b) for donations)."""

    permission_classes = [IsActiveStaff]
    confirm = True

    @extend_schema(tags=TAG, summary="Confirm or reject a gift's paid claim",
                   description="Confirming writes the offline receipt (maker-checker applies); rejecting leaves the "
                               "gift waiting. Needs `billing.offline_claims`.",
                   request=ClaimDecisionSerializer, responses={200: StaffClaimSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        from apps.payments import offline_claims
        from apps.payments.models import PaymentClaim

        from .gates import require_feature
        from .tax_receipts import payment_for

        donation = gift_or_404(request, makerspace_id, pk, record=True)
        require_feature(donation.makerspace, "billing.offline_claims")
        claim = PaymentClaim.objects.filter(payment=payment_for(donation), status__in=PaymentClaim.OPEN_STATUSES).first()
        if claim is None:
            raise NotFound({"detail": gettext("This gift has no open paid claim."), "code": "no_open_claim"})
        payload = ClaimDecisionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        if self.confirm:
            claim = offline_claims.confirm_claim(actor=request.user, makerspace_id=makerspace_id, claim_id=claim.pk)
        else:
            claim = offline_claims.reject_claim(actor=request.user, makerspace_id=makerspace_id, claim_id=claim.pk,
                                                note=payload.validated_data["note"])
        return Response(StaffClaimSerializer(claim).data)
