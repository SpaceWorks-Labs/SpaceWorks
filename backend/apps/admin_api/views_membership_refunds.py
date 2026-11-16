"""X20 for staff: the membership policy's suggested refund on a case being decided.

Same access as the refund-case detail (the charge's subject authority, through
`refund_case_access`). An estimate only: approval still takes staff's chosen amount and
moves money only through the approved case.
"""
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.views_roles import ERRORS
from apps.makerspaces.membership_refund_suggestion import suggestion
from apps.makerspaces.serializers_membership_l4 import RefundSuggestionSerializer


class RefundCaseMembershipSuggestionView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Suggested amount for a membership refund case",
                   description="What the membership refund policy suggests if the term were cancelled now. "
                               "`applies` is false for non-membership charges or when no policy is set.",
                   responses={200: RefundSuggestionSerializer, **ERRORS})
    def get(self, request, makerspace_id, case_id):
        from apps.payments.refund_case_access import get_visible_case, require_queue
        require_queue(request.user, makerspace_id)
        case = get_visible_case(request.user, makerspace_id, case_id)
        return Response(RefundSuggestionSerializer(suggestion(case.payment)).data)
