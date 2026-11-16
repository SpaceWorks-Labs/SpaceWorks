"""Shared response/error contracts for every literal reimbursement method."""
from drf_spectacular.utils import OpenApiParameter, PolymorphicProxySerializer
from apps.events.programme.serializers import ErrorSerializer
from .serializers_finance import ClaimRecommendationCommand, ClaimDecisionCommand
from .serializers_read import ClaimScreeningDetail, ClaimFinanceDetail, RequestPage, FinanceRequestPage

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 410, 413, 416, 423, 429, 503)}
TAGS = ["Event reimbursements"]
IDEMPOTENCY = [OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True,
    description="Must equal operation_id. Identical replay returns the original stable reference.")]
REVIEW = PolymorphicProxySerializer(component_name="ReimbursementClaimReviewCommand",
    serializers={"recommend": ClaimRecommendationCommand, "decide": ClaimDecisionCommand}, resource_type_field_name="mode")
CLAIM_DETAIL = PolymorphicProxySerializer(component_name="ReimbursementClaimDetail",
    serializers=[ClaimScreeningDetail, ClaimFinanceDetail], resource_type_field_name=None)
REQUEST_PAGE = PolymorphicProxySerializer(component_name="ReimbursementRequestPage",
    serializers=[RequestPage, FinanceRequestPage], resource_type_field_name=None)
FINANCE = "Host VIEW_FINANCE and a full browser session; mutations require recent session reauthentication."
