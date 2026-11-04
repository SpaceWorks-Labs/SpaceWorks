"""A signed-in giver's own gifts and pledges in one space (their own rows only).

The gift's charge is an ordinary member charge: it is paid from the member payments page
(the existing checkout) and a refund is asked for there too (it opens a case staff decide).
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenant_migration.gate_runtime import tenant_write

from . import serializers_public as s
from .gates import DONATIONS, PLEDGES, TAX, require_feature
from .models import Donation, DonationPledge
from .views_public import ERRORS

TAG = ["Donations"]


def member_space(makerspace_id, key=DONATIONS):
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.servability import servable_queryset

    space = servable_queryset(Makerspace.objects.filter(pk=makerspace_id)).first()
    if space is None:
        raise NotFound("Makerspace not found.")
    return require_feature(space, key)


class MemberDonationListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="My gifts to this space", responses={200: s.GiftStatusSerializer(many=True),
                                                                        **ERRORS})
    def get(self, request, makerspace_id):
        space = member_space(makerspace_id)
        from apps.accounts.staff_identity import actor_ids_for

        rows = Donation.objects.filter(makerspace=space, donor_id__in=actor_ids_for(request.user)).select_related(
            "makerspace", "campaign")
        return Response(s.GiftStatusSerializer([s.gift_status(row) for row in rows[:200]], many=True).data)


class MemberTaxReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="Download my 80G receipt (PDF)",
                   responses={(200, "application/pdf"): OpenApiResponse(OpenApiTypes.BINARY), **ERRORS})
    def get(self, request, makerspace_id, pk):
        from .tax_receipt_pdf import pdf_response

        space = require_feature(member_space(makerspace_id), TAX)
        from apps.accounts.staff_identity import actor_ids_for

        donation = Donation.objects.filter(makerspace=space, donor_id__in=actor_ids_for(request.user), pk=pk).first()
        if donation is None or not donation.tax_receipt:
            raise NotFound({"detail": "No tax-exempt receipt was issued for this gift.", "code": "no_tax_receipt"})
        return pdf_response(donation)


class MemberPledgeListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="My pledges to this space",
                   responses={200: s.PledgeStatusSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        from .serializers_staff import pledge_status

        space = member_space(makerspace_id, PLEDGES)
        rows = DonationPledge.objects.filter(makerspace=space, donor=request.user).select_related("makerspace",
                                                                                                  "campaign")
        return Response(s.PledgeStatusSerializer([pledge_status(row) for row in rows[:100]], many=True).data)


class MemberPledgeActionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="Pause, resume, change or cancel my pledge",
                   description="Audited `pledge.paused|resumed|updated|cancelled`.",
                   request=s.PledgeActionSerializer, responses={200: s.PledgeStatusSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        from .pledges import change_pledge
        from .serializers_staff import pledge_status
        from .services import clean_amount

        space = member_space(makerspace_id, PLEDGES)
        pledge = DonationPledge.objects.filter(makerspace=space, donor=request.user, pk=pk).first()
        if pledge is None:
            raise NotFound("Pledge not found.")
        payload = s.PledgeActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with tenant_write(space.pk):
            amount = clean_amount(space, data["amount"]) if data["amount"] is not None else None
            pledge = change_pledge(pledge, actor=request.user, action=data["action"], amount=amount,
                                   interval=data["interval"])
        return Response(s.PledgeStatusSerializer(pledge_status(pledge)).data)
