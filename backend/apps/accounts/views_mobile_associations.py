from django.http import Http404, JsonResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView

from apps.accounts.mobile_associations import (
    apple_association_document, assetlinks_document, association_host_kind,
)

ANDROID_DOCUMENT_SCHEMA = {
    "type": "array", "items": {"type": "object", "properties": {
        "relation": {"type": "array", "items": {"type": "string"}},
        "target": {"type": "object", "properties": {
            "namespace": {"type": "string"}, "package_name": {"type": "string"},
            "sha256_cert_fingerprints": {"type": "array", "items": {"type": "string"}},
        }},
    }},
}
APPLE_DOCUMENT_SCHEMA = {
    "type": "object", "properties": {
        "applinks": {"type": "object", "properties": {
            "apps": {"type": "array", "items": {"type": "string"}},
            "details": {"type": "array", "items": {"type": "object", "properties": {
                "appIDs": {"type": "array", "items": {"type": "string"}},
                "components": {"type": "array", "items": {"type": "object", "properties": {
                    "/": {"type": "string"}, "exclude": {"type": "boolean"},
                }}},
            }}},
        }},
        "webcredentials": {"type": "object", "properties": {
            "apps": {"type": "array", "items": {"type": "string"}},
        }},
    },
}
HOST_ERRORS = {400: OpenApiResponse(description="Managed host middleware refuses the host."),
               404: OpenApiResponse(description="Host is not an eligible frontend host.")}


class AssociationView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    renderer_classes = [JSONRenderer]
    throttle_classes = []
    http_method_names = ["get", "head", "options"]

    def response(self, request, builder):
        kind = association_host_kind(request.get_host())
        if kind is None:
            raise Http404
        response = JsonResponse(builder(kind), safe=False)
        response["Cache-Control"] = "public, max-age=300"
        return response


class AssetLinksView(AssociationView):
    @extend_schema(tags=["Mobile associations"], auth=[],
                   responses={200: ANDROID_DOCUMENT_SCHEMA, **HOST_ERRORS})
    def get(self, request):
        return self.response(request, lambda kind: assetlinks_document())


class AppleAppSiteAssociationView(AssociationView):
    @extend_schema(tags=["Mobile associations"], auth=[],
                   responses={200: APPLE_DOCUMENT_SCHEMA, **HOST_ERRORS})
    def get(self, request):
        return self.response(request, apple_association_document)
