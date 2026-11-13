"""Signatory routes (C4): staff set up to three signatories; each signatory approves designs."""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.events.credentials.views import ERRORS
from apps.events.profile_photos.views import private
from apps.events.throttles import CredentialRenderThrottle
from . import signatory_commands as commands
from .owner_queries import require_member_space
from .signatories import approval_required, current_designs, design_status, released
from .signatory_serializers import (CertificateApprovalResultSerializer, CertificateApproveSerializer, CertificatePendingApprovalSerializer,
                                    CertificateSignatoryCandidateSerializer, CertificateSignatoryPolicySerializer,
                                    CertificateSignatoryStateSerializer, CertificateSignatoryWriteSerializer)

TAGS = ["Event certificates"]


def _event(request, pk):
    from apps.events import event_authority
    from apps.events.event_permissions import EDIT_DETAILS
    from apps.events.services_certificate_templates import require_design
    event = event_authority.get_event(request.user, pk, EDIT_DETAILS)
    require_design(event, request.user)
    return event


def state(event):
    from .signatory_models import EventCertificateSignatory
    rows = EventCertificateSignatory.objects.select_related("member").filter(event=event)
    designs = [design for design in current_designs(event) if design_status(event, design)]
    return {"approval_required": approval_required(event), "signatories": [{
        "id": row.pk, "slot": row.slot, "name": row.name, "title": row.title, "member_id": row.member_id,
        "member_name": (row.member.display_name or row.member.get_full_name() or row.member.username)
        if row.member_id else None, "signature_artwork_id": row.signature_id, "version": row.version}
        for row in rows], "designs": [{
        "template_revision_id": design.pk, "certificate_kind": design.certificate_kind,
        "slots": design_status(event, design), "released": released(event, design)} for design in designs]}


class SignatoryListView(APIView):
    permission_classes = [IsActiveStaff]

    def _respond(self, request, event, status=200):
        context = {"request": request, "makerspace_id": event.makerspace_id}
        return private(Response(CertificateSignatoryStateSerializer(state(event), context=context).data, status=status))

    @extend_schema(tags=TAGS, responses={200: CertificateSignatoryStateSerializer, **ERRORS},
                   description="Signatories, the approval switch and each current design's approvals. "
                               "Requires edit_details and events.certificate_designer.")
    def get(self, request, pk):
        return self._respond(request, _event(request, pk))

    @extend_schema(tags=TAGS, request=CertificateSignatoryWriteSerializer, responses={200: CertificateSignatoryStateSerializer, **ERRORS},
                   description="Add or change the signatory in one slot (1-3). A change asks for fresh approvals.")
    def post(self, request, pk):
        event = _event(request, pk)
        serializer = CertificateSignatoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        commands.save_signatory(event, actor=request.user, **serializer.validated_data)
        return self._respond(request, event)


class SignatoryDetailView(SignatoryListView):
    # Inherits the list view's helpers only. Its GET/POST take no `slot`, so exposing them on the
    # `.../signatories/<slot>/` route answered 500 (TypeError); only DELETE belongs here.
    http_method_names = ["delete", "options"]

    @extend_schema(tags=TAGS, responses={200: CertificateSignatoryStateSerializer, **ERRORS},
                   description="Remove a signatory. 409 signatory_in_use while a current design prints them.")
    def delete(self, request, pk, slot):
        event = _event(request, pk)
        commands.remove_signatory(event, actor=request.user, slot=slot)
        return self._respond(request, event)


class SignatoryPolicyView(SignatoryListView):
    @extend_schema(tags=TAGS, request=CertificateSignatoryPolicySerializer, responses={200: CertificateSignatoryStateSerializer, **ERRORS},
                   description="Require (or stop requiring) every printed signatory to approve a design before "
                               "its certificates render or are emailed. Default off.")
    def post(self, request, pk):
        event = _event(request, pk)
        serializer = CertificateSignatoryPolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        commands.set_approval_required(event, actor=request.user, **serializer.validated_data)
        return self._respond(request, event)


class SignatoryCandidatesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, responses={200: CertificateSignatoryCandidateSerializer(many=True), **ERRORS},
                   parameters=[OpenApiParameter("q", str, required=True, description="At least two characters.")],
                   description="Active accounts of this space a signatory can be linked to (at most 10).")
    def get(self, request, pk):
        from apps.accounts.models import User
        from apps.accounts.staff_identity import person_q
        from django.db.models import Q
        event = _event(request, pk)
        term = request.query_params.get("q", "").strip()[:80]
        rows = []
        if len(term) >= 2:
            rows = User.objects.filter(person_q(), is_active=True, access_status="active", retired_at__isnull=True).filter(
                makerspace_memberships__makerspace_id=event.makerspace_id,
                makerspace_memberships__status="active").filter(
                Q(display_name__icontains=term) | Q(first_name__icontains=term) | Q(last_name__icontains=term)
                | Q(username__icontains=term)).distinct().order_by("display_name", "pk")[:10]
        data = [{"id": row.pk, "name": row.display_name or row.get_full_name() or row.username} for row in rows]
        context = {"request": request, "makerspace_id": event.makerspace_id}
        return private(Response(CertificateSignatoryCandidateSerializer(data, many=True, context=context).data))


class MemberApprovalListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, responses={200: CertificatePendingApprovalSerializer(many=True), **ERRORS},
                   description="Certificate designs that print your signature in this space, approved or waiting.")
    def get(self, request, makerspace_id):
        require_member_space(request.user, makerspace_id)
        return private(Response(CertificatePendingApprovalSerializer(commands.pending_for(request.user, makerspace_id), many=True).data))


class MemberApprovalPreviewView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=TAGS, responses={(200, "application/pdf"): OpenApiResponse(OpenApiTypes.BINARY), **ERRORS},
                   description="The design you are asked to approve, rendered with a sample recipient.")
    def get(self, request, makerspace_id, signatory_id, revision_id):
        from types import SimpleNamespace
        from django.utils import timezone
        from apps.events.certificate_rendering import render_certificate_pdf
        from apps.events.certificate_templates import issuance_layout
        from .merge import sample_merge
        from .signatories import preview_signatures
        from .signatory_models import EventCertificateSignatory
        require_member_space(request.user, makerspace_id)
        signatory = get_object_or_404(EventCertificateSignatory.objects.select_related("event__makerspace"),
                                      pk=signatory_id, member=request.user, event__makerspace_id=makerspace_id)
        event = signatory.event
        revision = get_object_or_404(event.certificate_template_revisions.select_related("artwork"), pk=revision_id)
        snapshot = issuance_layout(revision)
        snapshot["merge"] = sample_merge(revision.certificate_kind or "attendance")
        preview_signatures(event, snapshot)
        context = SimpleNamespace(layout_snapshot=snapshot, recipient_name="Sample attendee",
                                  kind=revision.certificate_kind or "attendance", award_id=None,
                                  event_title=event.title, issuer_name=event.makerspace.name,
                                  event_timezone_name=event.timezone_name, event_starts_at=event.starts_at,
                                  event_ends_at=event.ends_at, issued_at=timezone.now(), serial="PREVIEW", revision=0)
        return private(HttpResponse(render_certificate_pdf(context), content_type="application/pdf"))


class MemberApproveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, request=CertificateApproveSerializer, responses={200: CertificateApprovalResultSerializer, **ERRORS},
                   description="Approve a design that prints your signature, with your current name, title and image.")
    def post(self, request, makerspace_id, signatory_id):
        from .signatory_models import EventCertificateSignatory
        require_member_space(request.user, makerspace_id)
        serializer = CertificateApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        signatory = get_object_or_404(EventCertificateSignatory, pk=signatory_id, member=request.user,
                                      event__makerspace_id=makerspace_id)
        row = commands.approve(signatory.event_id, actor=request.user, signatory_id=signatory.pk,
                               **serializer.validated_data)
        return private(Response({"id": row.pk, "approved_at": row.approved_at}))
