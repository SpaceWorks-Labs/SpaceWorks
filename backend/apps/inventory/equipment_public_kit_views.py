from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from django.http import Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.inventory.equipment_public_kits import PublicKit, PublicKitPage, kit_detail, kit_page
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.guards import require_module_for_servable
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.request_access import require_current_term
from apps.presence.guard import require_active_account, require_active_member_presence


def _maker(request, slug):
    maker = get_public_makerspace(slug)
    if not maker.public_site_enabled or not maker.public_inventory_enabled:
        raise Http404
    # A consumable-only plan is independent of the loans capability.
    require_module_for_servable(maker, "public_inventory")
    if module_enabled(maker, "membership"):
        from apps.hardware_requests.guest_lending import admit_borrower
        admit_borrower(maker, request.user, planning=True)
    else:
        require_active_account(request.user, maker)
    return maker


class PublicKitListView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "public_request_submit"

    # Explicit IDs: the auto names of the list and detail GETs collide (`_retrieve_2`).
    @extend_schema(operation_id="api_v1_public_equipment_kits_list",
                   parameters=[OpenApiParameter("page", int, OpenApiParameter.QUERY, description="One-based page number.")],
                   responses={200: PublicKitPage, 401: OpenApiResponse(description="Authentication required."),
                              403: OpenApiResponse(description="Account or membership unavailable."),
                              404: OpenApiResponse(description="Makerspace unavailable."),
                              429: OpenApiResponse(description="Rate limit exceeded.")})
    def get(self, request, makerspace_slug):
        return kit_page(request, _maker(request, makerspace_slug))


class PublicKitDetailView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "public_request_submit"

    @extend_schema(operation_id="api_v1_public_equipment_kit_retrieve",
                   responses={200: PublicKit, 401: OpenApiResponse(description="Authentication required."),
                              403: OpenApiResponse(description="Account or membership unavailable."),
                              404: OpenApiResponse(description="Kit unavailable."),
                              429: OpenApiResponse(description="Rate limit exceeded.")})
    def get(self, request, makerspace_slug, kit_id):
        return Response(kit_detail(_maker(request, makerspace_slug), kit_id))
