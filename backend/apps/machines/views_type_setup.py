"""Staff API: a machine type's per-space setup -- booking defaults, training notes and documents (decision 343)."""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.evidence.storage import StorageUnavailable

from . import type_documents, type_setup
from .consumable_profile_services import space_and_type
from .models_type_setup import MachineTypeDocument, MachineTypeSetup
from .views_consumable_profiles import ERRORS, TAGS


class MachineTypeSetupSerializer(serializers.ModelSerializer):
    booking_slot_minutes = serializers.IntegerField(min_value=1, max_value=1440, allow_null=True, required=False)
    booking_buffer_before_minutes = serializers.IntegerField(min_value=0, max_value=1440, allow_null=True,
                                                             required=False)
    booking_buffer_after_minutes = serializers.IntegerField(min_value=0, max_value=1440, allow_null=True,
                                                            required=False)
    training_notes = serializers.CharField(allow_blank=True, required=False, max_length=type_setup.MAX_NOTES)

    class Meta:
        model = MachineTypeSetup
        fields = list(type_setup.FIELDS) + ["updated_at"]
        read_only_fields = ["updated_at"]


class MachineTypeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineTypeDocument
        fields = ["id", "title", "original_filename", "content_type", "size_bytes", "member_visible", "created_at"]


class TypeDocumentPresignSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)


class TypeDocumentPresignResultSerializer(serializers.Serializer):
    object_key = serializers.CharField()
    upload = serializers.DictField()


class TypeDocumentAttachSerializer(serializers.Serializer):
    object_key = serializers.CharField(max_length=255)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    original_filename = serializers.CharField(max_length=255)
    member_visible = serializers.BooleanField(default=True)


class AppliedSpacesSerializer(serializers.Serializer):
    spaces = serializers.ListField(child=serializers.IntegerField())


def _unavailable():
    return Response({"detail": gettext("Machine document storage is unavailable.")}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class TypeSetupView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="A machine type's booking defaults and training notes in this space",
                   responses={200: MachineTypeSetupSerializer, **ERRORS})
    def get(self, request, makerspace_id, type_id):
        space, machine_type = space_and_type(request.user, makerspace_id, type_id)
        return Response(MachineTypeSetupSerializer(type_setup.setup_for(space, machine_type)).data)

    @extend_schema(tags=TAGS, summary="Change a machine type's booking defaults and training notes",
                   request=MachineTypeSetupSerializer, responses={200: MachineTypeSetupSerializer, **ERRORS})
    def patch(self, request, makerspace_id, type_id):
        space, machine_type = space_and_type(request.user, makerspace_id, type_id, write=True)
        payload = MachineTypeSetupSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        row = type_setup.update(request.user, space, machine_type, payload.validated_data)
        return Response(MachineTypeSetupSerializer(row).data)


class TypeBookingDefaultsApplyView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Apply the type's booking defaults to its existing bookable spaces",
                   description="Each space is updated through the bookings rule service, which re-checks your "
                               "booking authority.", request=None, responses={200: AppliedSpacesSerializer, **ERRORS})
    def post(self, request, makerspace_id, type_id):
        space, machine_type = space_and_type(request.user, makerspace_id, type_id, write=True)
        return Response({"spaces": type_setup.apply_booking_defaults(request.user, space, machine_type)})


class TypeDocumentsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="A machine type's documents in this space",
                   responses={200: MachineTypeDocumentSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id, type_id):
        space, machine_type = space_and_type(request.user, makerspace_id, type_id)
        rows = MachineTypeDocument.objects.filter(makerspace=space, machine_type=machine_type)
        return Response(MachineTypeDocumentSerializer(rows, many=True).data)

    @extend_schema(tags=TAGS, summary="Attach an uploaded document to a machine type (counts against storage)",
                   request=TypeDocumentAttachSerializer, responses={201: MachineTypeDocumentSerializer, **ERRORS})
    def post(self, request, makerspace_id, type_id):
        space, machine_type = space_and_type(request.user, makerspace_id, type_id, write=True)
        payload = TypeDocumentAttachSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            row = type_documents.attach(request.user, space, machine_type, **payload.validated_data)
        except StorageUnavailable:
            return _unavailable()
        return Response(MachineTypeDocumentSerializer(row).data, status=status.HTTP_201_CREATED)


class TypeDocumentPresignView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Presign a private upload for a machine type document",
                   request=TypeDocumentPresignSerializer, responses={201: TypeDocumentPresignResultSerializer, **ERRORS})
    def post(self, request, makerspace_id, type_id):
        space, _machine_type = space_and_type(request.user, makerspace_id, type_id, write=True)
        payload = TypeDocumentPresignSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            object_key, upload = type_documents.presign(space, payload.validated_data["content_type"],
                                                        payload.validated_data["filename"])
        except StorageUnavailable:
            return _unavailable()
        return Response({"object_key": object_key, "upload": upload}, status=status.HTTP_201_CREATED)


class TypeDocumentUrlSerializer(serializers.Serializer):
    url = serializers.CharField()


class TypeDocumentDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="A short-lived signed link to a machine type document",
                   responses={200: TypeDocumentUrlSerializer, **ERRORS})
    def get(self, request, makerspace_id, type_id, pk):
        space, machine_type = space_and_type(request.user, makerspace_id, type_id)
        row = get_object_or_404(MachineTypeDocument, makerspace=space, machine_type=machine_type, pk=pk)
        try:
            return Response({"url": type_documents.signed_url(row)})
        except StorageUnavailable:
            return _unavailable()

    @extend_schema(tags=TAGS, summary="Remove a machine type document (frees its storage)", request=None,
                   responses={204: None, **ERRORS})
    def delete(self, request, makerspace_id, type_id, pk):
        space, machine_type = space_and_type(request.user, makerspace_id, type_id, write=True)
        type_documents.remove(request.user, get_object_or_404(
            MachineTypeDocument, makerspace=space, machine_type=machine_type, pk=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
