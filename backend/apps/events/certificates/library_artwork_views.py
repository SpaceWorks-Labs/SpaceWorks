from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.admin_api.permissions import IsActiveStaff
from apps.events.credentials.views import ERRORS
from apps.events.serializers_certificate_templates import (CertificateArtworkPresignSerializer,
    CertificateArtworkUploadSerializer, CertificateArtworkSerializer)
from apps.events.serializers_staff_tools import StrictSerializer
from apps.events.profile_photos.views import private
from apps.events.throttles import CertificateArtworkThrottle
from .library_artwork import reserve, finalize


class LibraryArtworkReserveView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CertificateArtworkThrottle]

    @extend_schema(tags=["Event certificate library"], request=CertificateArtworkPresignSerializer,
                   responses={201: CertificateArtworkUploadSerializer, **ERRORS})
    def post(self, request, makerspace_id, template_id):
        serializer = CertificateArtworkPresignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        row, url = reserve(makerspace_id, template_id, actor=request.user, **values)
        return private(Response({"id": row.pk, "upload_url": url, "headers": {
            "Content-Type": values["content_type"]}}, status=201))


class LibraryArtworkFinalizeView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CertificateArtworkThrottle]

    @extend_schema(tags=["Event certificate library"], request=StrictSerializer,
                   responses={200: CertificateArtworkSerializer, **ERRORS})
    def post(self, request, makerspace_id, template_id, artwork_id):
        serializer = StrictSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = finalize(makerspace_id, template_id, artwork_id, actor=request.user)
        return private(Response({"id": row.pk, "resource_id": row.resource_id}))
