"""Member API: a machine type's training notes and documents (decision 343 follow-up).

Only for an active member of the space (`active_membership`), only member-visible documents, and only
types usable there (global or the space's own). The flags tell the app where to show the notes: the type
page always, session start and the job request when the space chose so.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.evidence.storage import StorageUnavailable
from apps.makerspaces.guards import require_module
from apps.makerspaces.member_activity_service import active_membership
from apps.openapi_errors import errors

from . import type_documents, type_setup
from .models import MachineType
from .models_type_setup import MachineTypeDocument
from .views_type_setup import TypeDocumentUrlSerializer, _unavailable


class GuideDocumentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    content_type = serializers.CharField()
    size_bytes = serializers.IntegerField()


class MachineTypeGuideSerializer(serializers.Serializer):
    machine_type_id = serializers.IntegerField()
    machine_type_name = serializers.CharField()
    training_notes = serializers.CharField(allow_blank=True)
    notes_at_session_start = serializers.BooleanField()
    notes_at_job_request = serializers.BooleanField()
    documents = GuideDocumentSerializer(many=True)


def _member_space(user, makerspace_id):
    membership = active_membership(user, makerspace_id)
    if membership is None:
        raise PermissionDenied()
    require_module(membership.makerspace, "machines")
    return membership.makerspace


class MemberTypeGuideView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member machines"], summary="A machine type's training notes and documents",
                   responses={200: MachineTypeGuideSerializer, **errors(403, 404)})
    def get(self, request, makerspace_id, type_id):
        space = _member_space(request.user, makerspace_id)
        machine_type = MachineType.objects.filter(pk=type_id).filter(makerspace__isnull=True).first() or \
            MachineType.objects.filter(pk=type_id, makerspace=space).first()
        if machine_type is None:
            raise NotFound()
        setup = type_setup.setup_for(space, machine_type)
        return Response(MachineTypeGuideSerializer({
            "machine_type_id": machine_type.pk, "machine_type_name": machine_type.name,
            "training_notes": setup.training_notes, "notes_at_session_start": setup.notes_at_session_start,
            "notes_at_job_request": setup.notes_at_job_request,
            "documents": type_documents.member_documents(space, machine_type)}).data)


class MemberTypeDocumentUrlView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member machines"], summary="A short-lived signed link to a machine type document",
                   responses={200: TypeDocumentUrlSerializer, **errors(403, 404, 503)})
    def get(self, request, pk):
        row = get_object_or_404(MachineTypeDocument, pk=pk, member_visible=True)
        _member_space(request.user, row.makerspace_id)
        try:
            return Response({"url": type_documents.signed_url(row)})
        except StorageUnavailable:
            return _unavailable()
