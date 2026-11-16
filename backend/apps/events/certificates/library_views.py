from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.accounts import rbac
from apps.events import event_authority
from apps.events.credentials.views import CredentialCommandSerializer, ERRORS
from apps.events.serializers_certificate_templates import CertificateParametersSerializer
from apps.events.serializers_staff_tools import StrictSerializer
from apps.events.profile_photos.views import private
from apps.makerspaces.models import Makerspace
from . import library
from .library_models import EventCertificateLibraryTemplate as Template, EventCertificateLibraryRevision as Revision


class LibraryWriteSerializer(CredentialCommandSerializer):
    name = serializers.CharField(max_length=120)
    parameters = CertificateParametersSerializer()
    artwork_id = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)


class LibraryTemplateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    version = serializers.IntegerField()
    archived = serializers.BooleanField()


class LibraryRevisionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    parameters = CertificateParametersSerializer()
    artwork_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()


class LibrarySaveResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    version = serializers.IntegerField()
    revision_id = serializers.IntegerField()
    parameters = CertificateParametersSerializer()
    artwork_id = serializers.IntegerField(allow_null=True)


class CopyLibrarySerializer(CredentialCommandSerializer):
    event_id = serializers.IntegerField(min_value=1)
    revision_id = serializers.IntegerField(min_value=1)


class CaptureLibrarySerializer(CopyLibrarySerializer):
    name = serializers.CharField(max_length=120)
    template_id = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)


class LibraryPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = LibraryTemplateSerializer(many=True)


class LibraryRevisionPageSerializer(LibraryPageSerializer):
    results = LibraryRevisionSerializer(many=True)


def space_for(request, makerspace_id):
    space = get_object_or_404(rbac.scope_by_makerspace(request.user, Makerspace.objects.all(), "pk"), pk=makerspace_id)
    event_authority.require_tenant(request.user, space)
    return space


class LibraryListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event certificate library"], responses={200: LibraryPageSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = space_for(request, makerspace_id)
        pagination = PageNumberPagination()
        pagination.page_size = 24
        rows = pagination.paginate_queryset(Template.objects.filter(makerspace=space).order_by("pk"), request)
        return private(pagination.get_paginated_response(LibraryTemplateSerializer(rows, many=True).data))

    @extend_schema(tags=["Event certificate library"], request=LibraryWriteSerializer,
                   responses={201: LibrarySaveResultSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space_for(request, makerspace_id)
        serializer = LibraryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return private(Response(library.save(makerspace_id, actor=request.user, **serializer.validated_data), status=201))


class LibraryDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event certificate library"], responses={200: LibraryTemplateSerializer, **ERRORS})
    def get(self, request, makerspace_id, template_id):
        space = space_for(request, makerspace_id)
        return private(Response(LibraryTemplateSerializer(get_object_or_404(Template, makerspace=space, pk=template_id)).data))

    @extend_schema(tags=["Event certificate library"], request=LibraryWriteSerializer,
                   responses={200: LibrarySaveResultSerializer, **ERRORS})
    def patch(self, request, makerspace_id, template_id):
        serializer = LibraryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return private(Response(library.save(makerspace_id, actor=request.user, template_id=template_id, **serializer.validated_data)))


class LibraryRevisionsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event certificate library"], responses={200: LibraryRevisionPageSerializer, **ERRORS})
    def get(self, request, makerspace_id, template_id):
        space = space_for(request, makerspace_id)
        template = get_object_or_404(Template, makerspace=space, pk=template_id)
        pagination = PageNumberPagination()
        pagination.page_size = 24
        rows = pagination.paginate_queryset(template.revisions.all(), request)
        return private(pagination.get_paginated_response(LibraryRevisionSerializer(rows, many=True).data))


class LibraryRevisionView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event certificate library"], responses={200: LibraryRevisionSerializer, **ERRORS})
    def get(self, request, makerspace_id, template_id, revision_id):
        space = space_for(request, makerspace_id)
        row = get_object_or_404(Revision, template__makerspace=space, template_id=template_id, pk=revision_id)
        return private(Response(LibraryRevisionSerializer(row).data))


class LibraryCopyView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event certificate library"], request=CopyLibrarySerializer,
                   responses={200: LibraryRevisionSerializer, **ERRORS})
    def post(self, request, makerspace_id, template_id):
        serializer = CopyLibrarySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = library.copy_to_event(makerspace_id, actor=request.user, template_id=template_id, **serializer.validated_data)
        return private(Response(LibraryRevisionSerializer(row).data))


class LibraryCaptureView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event certificate library"], request=CaptureLibrarySerializer,
                   responses={201: LibrarySaveResultSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        from .library_capture import capture
        serializer = CaptureLibrarySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return private(Response(capture(makerspace_id, actor=request.user, **serializer.validated_data), status=201))
