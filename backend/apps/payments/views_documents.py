"""Authenticated, tenant-scoped document metadata and expiring PDF grants."""

from django.utils.translation import gettext
from django.core import signing
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, active_user
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.payments.document_delivery import DOWNLOAD_TTL, SALT, download_path
from apps.payments.member_access import member_may_see_own_charges
from apps.payments.member_scope import member_payment_queryset
from apps.payments.models import PaymentDocument
from apps.makerspaces.origin_scope import object_in_staff_origin_scope


class PaymentDocumentSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    def get_status(self, document) -> str:
        from .document_snapshot import bill_status
        return bill_status(document)

    class Meta:
        model = PaymentDocument
        fields = ("id", "payment", "number", "kind", "issued_at", "money_at", "amount", "currency", "status")


class DocumentPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PaymentDocumentSerializer(many=True)


class DownloadGrantSerializer(serializers.Serializer):
    url = serializers.CharField()
    expires_in = serializers.IntegerField()


ERRORS = {code: OpenApiResponse(ErrorSerializer) for code in (400, 401, 403, 404)}


class DocumentPdfUnavailable(APIException):
    status_code = 503
    default_code = "document_pdf_unavailable"
    default_detail = "The document PDF is temporarily unavailable. Try again."


def scoped_documents(user, makerspace_id, audience):
    if audience == "staff":
        if not active_user(user):
            raise PermissionDenied(gettext("An active staff account is required."))
        if rbac.can(user, rbac.Action.VIEW_FINANCE, makerspace_id):
            return rbac.scope_by_action(user, rbac.Action.VIEW_FINANCE, PaymentDocument.objects.all(),
                                        field="makerspace_id").filter(makerspace_id=makerspace_id)
        # Audit 0.12.0 C-6 (decisions 241, 242(a)): an area owner who settles or refunds their
        # own area's charges reads those charges' bills, receipts and credit notes -- the same
        # rows the own-area queue admits (machine-type narrowed, never donations).
        from apps.payments.area_queue import area_payments
        return PaymentDocument.objects.filter(
            makerspace_id=makerspace_id, payment__in=area_payments(user, makerspace_id).values("pk"))
    if not member_may_see_own_charges(user, makerspace_id):
        raise PermissionDenied(gettext("An active membership or an existing charge is required."))
    return PaymentDocument.objects.filter(payment__in=member_payment_queryset(user, makerspace_id))


class MemberDocumentListView(APIView):
    permission_classes = [IsAuthenticated]
    audience = "member"

    @extend_schema(tags=["Payments"], summary="List scoped payment documents", request=None,
                   parameters=[OpenApiParameter("page", int), OpenApiParameter("kind", str,
                       enum=["receipt", "credit_note", "bill"])], responses={200: DocumentPageSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        rows = scoped_documents(request.user, makerspace_id, self.audience).order_by("-issued_at", "-pk")
        kind = request.query_params.get("kind")
        if kind is not None:
            if kind not in PaymentDocument.Kind.values:
                raise ValidationError({"detail": gettext("Unknown document kind."), "code": "document_kind_invalid"})
            rows = rows.filter(kind=kind)
        paginator = PageNumberPagination()
        paginator.page_size = 24
        from .document_snapshot import with_live_status
        rows = with_live_status(rows)
        page = paginator.paginate_queryset(rows, request)
        return paginator.get_paginated_response(PaymentDocumentSerializer(page, many=True).data)


class StaffDocumentListView(MemberDocumentListView):
    permission_classes = [IsActiveStaff]
    audience = "staff"


class MemberDocumentGrantView(APIView):
    permission_classes = [IsAuthenticated]
    audience = "member"

    @extend_schema(tags=["Payments"], summary="Get a user-bound five-minute PDF download URL",
                   request=None, responses={200: DownloadGrantSerializer, **ERRORS})
    def get(self, request, makerspace_id, document_id):
        document = get_object_or_404(scoped_documents(request.user, makerspace_id, self.audience), pk=document_id)
        return Response({"url": download_path(document, request.user, makerspace_id=makerspace_id,
                                              audience=self.audience), "expires_in": DOWNLOAD_TTL})


class StaffDocumentGrantView(MemberDocumentGrantView):
    permission_classes = [IsActiveStaff]
    audience = "staff"


class DocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Payments"], summary="Download an issued payment document PDF",
                   request=None, parameters=[OpenApiParameter("token", str, required=True)],
                   responses={(200, "application/pdf"): OpenApiTypes.BINARY,
                              503: OpenApiResponse(ErrorSerializer), **ERRORS})
    def get(self, request, document_id):
        try:
            grant = signing.loads(request.query_params.get("token", ""), salt=SALT, max_age=DOWNLOAD_TTL)
        except signing.BadSignature:
            raise ValidationError({"detail": gettext("Download URL is invalid or expired."), "code": "document_url_expired"})
        if grant["user"] != request.user.pk or grant["document"] != document_id:
            raise PermissionDenied()
        document = get_object_or_404(scoped_documents(request.user, grant["space"], grant["audience"]), pk=document_id)
        if grant["audience"] == "staff" and not object_in_staff_origin_scope(request, document):
            raise PermissionDenied(gettext("Document is outside this staff origin's makerspace."))
        from apps.payments.document_pdf import render_document_pdf
        try:
            payload = render_document_pdf(document)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("payment_document_render_failed", extra={
                "document_id": document.pk, "failure_type": type(exc).__name__,
            })
            raise DocumentPdfUnavailable() from exc
        response = HttpResponse(payload, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="payment-document-{document.pk}.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response
