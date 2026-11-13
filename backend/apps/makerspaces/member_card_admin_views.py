"""Staff console: issue, reissue, revoke, print, resolve and template member cards.

Gated by ACTIONS (`MANAGE_MEMBER_CARDS`, `SCAN_MEMBER_CARDS`), scoped through `rbac`.
"""
from django.utils.translation import gettext
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces import member_card_services, member_card_templates
from apps.makerspaces.guards import require_module
from apps.makerspaces.member_card_serializers import (
    MemberCardIssueSerializer,
    MemberCardPrintSerializer,
    MemberCardReissueSerializer,
    MemberCardResolveResultSerializer,
    MemberCardResolveSerializer,
    MemberCardRevokeSerializer,
    MemberCardSerializer,
    MemberCardTemplateSerializer,
)
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MemberCard

ERRORS = {
    400: OpenApiResponse(ErrorSerializer, description="Invalid card input."),
    401: OpenApiResponse(ErrorSerializer, description="Authentication required."),
    403: OpenApiResponse(ErrorSerializer, description="Missing member-card action or inactive account."),
    404: OpenApiResponse(ErrorSerializer, description="Not found in the permitted makerspace, or the membership module is turned off."),
}
TAG = "Admin memberships"


def _makerspace_for(actor, action, makerspace_id):
    makerspace = get_object_or_404(
        rbac.scope_by_action(actor, action, Makerspace.objects.all(), field="id"), pk=makerspace_id
    )
    require_module(makerspace, "membership")
    return makerspace


def _card_for(actor, action, pk):
    card = get_object_or_404(
        rbac.scope_by_action(actor, action, MemberCard.objects.select_related("makerspace", "membership__assigned_role")),
        pk=pk,
    )
    # The same gate `_makerspace_for` applies to list/issue/sheet/resolve: reissue mints a
    # fresh QR and print renders a PDF, so neither may run on a space without the module.
    # Revocation that follows a MEMBERSHIP revocation does not come through here -- it is
    # core RBAC state and must redact the card whether or not the module is installed.
    require_module(card.makerspace, "membership")
    return card


class _Pagination(PageNumberPagination):
    page_size = 24


class MemberCardListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="List member cards", request=None,
                   parameters=[OpenApiParameter("status", str, OpenApiParameter.QUERY, description="active | revoked")],
                   responses={200: MemberCardSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        makerspace = _makerspace_for(request.user, rbac.Action.SCAN_MEMBER_CARDS, makerspace_id)
        queryset = MemberCard.objects.filter(makerspace=makerspace).select_related("membership__user")
        wanted = request.query_params.get("status")
        if wanted == "active":
            queryset = queryset.filter(revoked_at__isnull=True, membership__isnull=False)
        elif wanted == "revoked":
            queryset = queryset.filter(revoked_at__isnull=False)
        paginator = _Pagination()
        page = paginator.paginate_queryset(queryset.order_by("card_number"), request, view=self)
        return paginator.get_paginated_response(MemberCardSerializer(page, many=True).data)


class MemberCardIssueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Issue a card to a membership", request=MemberCardIssueSerializer,
                   responses={201: MemberCardSerializer, **ERRORS})
    def post(self, request, makerspace_id, membership_id):
        makerspace = _makerspace_for(request.user, rbac.Action.MANAGE_MEMBER_CARDS, makerspace_id)
        membership = get_object_or_404(MakerspaceMembership, pk=membership_id, makerspace=makerspace)
        serializer = MemberCardIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        card = member_card_services.issue_card(
            request.user, membership, printed_name=serializer.validated_data.get("printed_name", "")
        )
        return Response(MemberCardSerializer(card).data, status=status.HTTP_201_CREATED)


class MemberCardReissueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Reissue (rotate the QR of) a card", request=MemberCardReissueSerializer,
                   responses={200: MemberCardSerializer, **ERRORS})
    def post(self, request, pk):
        card = _card_for(request.user, rbac.Action.MANAGE_MEMBER_CARDS, pk)
        serializer = MemberCardReissueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        card = member_card_services.reissue_card(request.user, card, reason=serializer.validated_data["reason"])
        return Response(MemberCardSerializer(card).data)


class MemberCardRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Revoke a card (redacts name and photo)", request=MemberCardRevokeSerializer,
                   responses={200: MemberCardSerializer, **ERRORS})
    def post(self, request, pk):
        card = _card_for(request.user, rbac.Action.MANAGE_MEMBER_CARDS, pk)
        serializer = MemberCardRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        card = member_card_services.revoke_card(request.user, card, reason=serializer.validated_data.get("reason") or "revoked",
                                                note=serializer.validated_data["note"])
        return Response(MemberCardSerializer(card).data)


def _pdf_response(pdf, filename):
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class MemberCardPrintView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Print one card (stock-size PDF, front and back)", request=None,
                   responses={(200, "application/pdf"): OpenApiTypes.BINARY, **ERRORS})
    def post(self, request, pk):
        from apps.card_designs.cards import render
        card = _card_for(request.user, rbac.Action.MANAGE_MEMBER_CARDS, pk)
        if not card.is_active:
            raise PermissionDenied(gettext("A revoked card cannot be printed."))
        pdf, _content_type, filename = render("member_card", card, fmt="pdf")
        member_card_services.record_print(request.user, [card])
        return _pdf_response(pdf, filename)


SYNC_SHEET_LIMIT = 10


class MemberCardSheetView(APIView):
    """One A4/Letter page renders in the request; larger sheets are a print job (#133)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Print one sheet of up to 10 cards (larger runs: queue a print job)",
                   request=MemberCardPrintSerializer, responses={(200, "application/pdf"): OpenApiTypes.BINARY, **ERRORS})
    def post(self, request, makerspace_id):
        from apps.card_designs.cards import context_for, document_for
        from apps.card_designs.sheets import render_sheets
        makerspace = _makerspace_for(request.user, rbac.Action.MANAGE_MEMBER_CARDS, makerspace_id)
        serializer = MemberCardPrintSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cards = MemberCard.objects.filter(makerspace=makerspace, revoked_at__isnull=True, membership__isnull=False).select_related("makerspace", "membership__assigned_role")
        ids = serializer.validated_data.get("card_ids")
        if ids:
            cards = cards.filter(pk__in=ids)
        if cards.count() > SYNC_SHEET_LIMIT:
            raise ValidationError({"detail": gettext('More than {SYNC_SHEET_LIMIT} cards: queue a print job instead.').format(SYNC_SHEET_LIMIT=SYNC_SHEET_LIMIT)})
        cards = list(cards.order_by("card_number"))
        if not cards:
            raise ValidationError({"detail": gettext("No active cards to print.")})
        rendered = []
        for card in cards:
            document = document_for("member_card", card)
            rendered.append((document, context_for("member_card", card, document)))
        page = member_card_templates.template_for(makerspace).get("page", "a4")
        if serializer.validated_data["preset"] == "single" or page == "cr80":
            pdf = _card_size_pages(rendered)  # card-sized pages, for card printers
        else:
            pdf = render_sheets(rendered, paper=page, title="Member cards")
        member_card_services.record_print(request.user, cards)
        return _pdf_response(pdf, "member-cards.pdf")


def _card_size_pages(rendered):
    from io import BytesIO
    from pypdf import PdfReader, PdfWriter
    from apps.card_designs.rendering import render_pdf
    writer = PdfWriter()
    for document, context in rendered:
        for pdf_page in PdfReader(BytesIO(render_pdf(document, context, title="Member card"))).pages:
            writer.add_page(pdf_page)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class MemberCardResolveThrottle(ScopedRateThrottle):
    scope = "member_card_resolve"


class MemberCardResolveView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberCardResolveThrottle]

    @extend_schema(tags=[TAG], summary="Resolve a scanned member card to minimal identity",
                   request=MemberCardResolveSerializer, responses={200: MemberCardResolveResultSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        makerspace = _makerspace_for(request.user, rbac.Action.SCAN_MEMBER_CARDS, makerspace_id)
        serializer = MemberCardResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = member_card_services.resolve(request.user, makerspace, serializer.validated_data["payload"])
        except Http404:
            raise
        return Response(result)


class MemberCardTemplateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Read the card layout template", request=None,
                   responses={200: MemberCardTemplateSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        makerspace = _makerspace_for(request.user, rbac.Action.SCAN_MEMBER_CARDS, makerspace_id)
        return Response(member_card_templates.template_for(makerspace))

    @extend_schema(tags=[TAG], summary="Replace the card layout template", request=MemberCardTemplateSerializer,
                   responses={200: MemberCardTemplateSerializer, **ERRORS})
    def put(self, request, makerspace_id):
        makerspace = _makerspace_for(request.user, rbac.Action.MANAGE_MEMBER_CARDS, makerspace_id)
        serializer = MemberCardTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = member_card_templates.save_template(makerspace, serializer.validated_data)
        audit.record(request.user, "member_card.template_updated", makerspace=makerspace, target=makerspace, meta={"version": template["version"]})
        return Response(template)
