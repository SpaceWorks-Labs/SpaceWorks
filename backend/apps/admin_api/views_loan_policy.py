from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_loan_policy import ReturnPolicySerializer
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import require_module
from apps.makerspaces.models_loan_policy import MakerspaceLoanPolicy
from apps.makerspaces.servability import servable_queryset

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 423, 503)}
# The loan policy is a lending decision, so the Inventory Manager (EDIT_INVENTORY) owns it
# beside the Space Manager -- mirrored by `loan_policy_settings.update_loan_policy`.
POLICY_ACTIONS = (rbac.Action.MANAGE_MAKERSPACE, rbac.Action.EDIT_INVENTORY)


class ReturnPolicyView(APIView):
    permission_classes = [IsActiveStaff]

    def _makerspace(self, request, makerspace_id):
        for action in POLICY_ACTIONS:
            makerspace = rbac.scope_by_action(
                request.user, action, servable_queryset(), field="pk",
            ).filter(pk=makerspace_id).first()
            if makerspace is not None:
                return require_module(makerspace, "request_workflow")
        raise Http404

    @extend_schema(tags=["Admin makerspaces"], request=None,
                   responses={200: ReturnPolicySerializer, **ERRORS})
    def get(self, request, makerspace_id):
        makerspace = self._makerspace(request, makerspace_id)
        return Response(ReturnPolicySerializer(MakerspaceLoanPolicy.for_makerspace(makerspace)).data)

    @extend_schema(tags=["Admin makerspaces"], request=ReturnPolicySerializer,
                   responses={200: ReturnPolicySerializer, **ERRORS})
    def patch(self, request, makerspace_id):
        makerspace = self._makerspace(request, makerspace_id)
        from apps.makerspaces.loan_policy_settings import update_loan_policy
        policy = update_loan_policy(request.user, makerspace, request.data)
        return Response(ReturnPolicySerializer(policy).data)
