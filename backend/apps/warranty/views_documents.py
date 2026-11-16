from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.warranty.serializers import (
    WarrantyDocumentFinalizeSerializer,
    WarrantyDocumentPresignSerializer,
    WarrantyDocumentSerializer,
    WarrantyDocumentUploadResponseSerializer,
    WarrantyDocumentUrlSerializer,
)
from apps.warranty.access import enforce, resolve_document, resolve_warranty
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.warranty import services, storage


ERRORS = {401: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}


class WarrantyDocumentPresignView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin warranty"],
        summary="Create a warranty document upload URL",
        request=WarrantyDocumentPresignSerializer,
        responses={
            201: WarrantyDocumentUploadResponseSerializer,
            400: OpenApiResponse(description="Invalid document upload request."),
            **ERRORS,
            503: OpenApiResponse(description="Warranty document storage is unavailable."),
        },
    )
    def post(self, request, pk, *args, **kwargs):
        warranty = resolve_warranty(request.user, pk)
        enforce(request.user, warranty)
        serializer = WarrantyDocumentPresignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = services.presign_document(request.user, warranty, serializer.validated_data)
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(payload, status=status.HTTP_201_CREATED)


class WarrantyDocumentCreateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin warranty"],
        summary="List documents attached to a warranty",
        responses={200: WarrantyDocumentSerializer(many=True), **ERRORS},
    )
    def get(self, request, pk, *args, **kwargs):
        warranty = resolve_warranty(request.user, pk)
        enforce(request.user, warranty)
        documents = warranty.documents.order_by("-created_at", "-id")
        return Response(WarrantyDocumentSerializer(documents, many=True).data)

    @extend_schema(
        tags=["Admin warranty"],
        summary="Finalize an uploaded warranty document",
        request=WarrantyDocumentFinalizeSerializer,
        responses={
            201: WarrantyDocumentSerializer,
            400: OpenApiResponse(description="Invalid or duplicate warranty document."),
            **ERRORS,
            503: OpenApiResponse(description="Warranty document storage is unavailable."),
        },
    )
    def post(self, request, pk, *args, **kwargs):
        warranty = resolve_warranty(request.user, pk)
        enforce(request.user, warranty)
        serializer = WarrantyDocumentFinalizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = services.finalize_document(request.user, warranty, serializer.validated_data)
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(
            WarrantyDocumentSerializer(document).data,
            status=status.HTTP_201_CREATED,
        )


class WarrantyDocumentUrlView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin warranty"],
        summary="Create a signed warranty document view URL",
        responses={
            200: WarrantyDocumentUrlSerializer,
            **ERRORS,
            503: OpenApiResponse(description="Warranty document storage is unavailable."),
        },
    )
    def get(self, request, pk, *args, **kwargs):
        document = resolve_document(request.user, pk)
        enforce(request.user, document.warranty)
        try:
            url = storage.presigned_get_url(document.object_key)
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response({"url": url})


class WarrantyDocumentDeleteView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin warranty"],
        summary="Delete a warranty document",
        responses={204: None, **ERRORS},
    )
    def delete(self, request, pk, *args, **kwargs):
        document = resolve_document(request.user, pk)
        warranty = document.warranty
        enforce(request.user, warranty)
        services.delete_document(request.user, document)
        return Response(status=status.HTTP_204_NO_CONTENT)
