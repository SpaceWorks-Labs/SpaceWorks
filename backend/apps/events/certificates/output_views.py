"""Holder routes (C7-C9) and the public share image (C8)."""
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.credentials.views import ERRORS
from apps.events.profile_photos.views import private
from apps.events.throttles import CredentialRenderThrottle
from . import holder
from .owner_queries import require_member_space
from .output_serializers import HolderCertificateSerializer, CertificateHolderNameSerializer
from .verification import VerifyThrottle, verified_row

TAGS = ["Event certificates"]
PNG = OpenApiResponse(OpenApiTypes.BINARY, description="PNG image.")


def _own(request, makerspace_id, pk, *, active=True):
    from .owner_queries import owner_certificate
    require_member_space(request.user, makerspace_id)
    row = owner_certificate(request.user, makerspace_id, pk)
    if active and row.status != "active":
        raise NotFound()
    return row


def png_response(content, filename):
    response = private(HttpResponse(content, content_type="image/png"))
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class MyCertificatesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, responses={200: HolderCertificateSerializer(many=True), **ERRORS},
                   description="Your certificates issued through this space, every kind, newest first.")
    def get(self, request, makerspace_id):
        require_member_space(request.user, makerspace_id)
        rows = [holder.project(row) for row in holder.owned(request.user, makerspace_id)[:200]]
        return private(Response(HolderCertificateSerializer(rows, many=True).data))


class MyCertificatePngView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=TAGS, responses={(200, "image/png"): PNG, **ERRORS},
                   description="Your issued certificate as a 300 dpi PNG, rasterised from the issued PDF. Audited.")
    def get(self, request, makerspace_id, pk):
        from .outputs import certificate_png
        row = _own(request, makerspace_id, pk)
        content = certificate_png(row)
        holder.record_png(row, actor=request.user)
        return png_response(content, f"certificate-{row.serial}.png")


class MyCertificateShareImageView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=TAGS, responses={(200, "image/png"): PNG, **ERRORS},
                   description="A 1200 x 627 share image (no QR code; your name only if you chose to show it). Audited.")
    def get(self, request, makerspace_id, pk):
        from .outputs import share_image
        row = _own(request, makerspace_id, pk)
        content = share_image(row)
        holder.record_share_image(row, actor=request.user)
        return png_response(content, f"certificate-{row.serial}-share.png")


class MyCertificateHolderNameView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, request=CertificateHolderNameSerializer, responses={200: HolderCertificateSerializer, **ERRORS},
                   description="Show or hide your name on this certificate's public verification page and share image. "
                               "Off by default; audited.")
    def post(self, request, makerspace_id, pk):
        row = _own(request, makerspace_id, pk, active=False)
        serializer = CertificateHolderNameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = holder.set_holder_name(row, actor=request.user, show=serializer.validated_data["show"])
        return private(Response(HolderCertificateSerializer(holder.project(row)).data))


class PublicShareImageView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [VerifyThrottle]

    @extend_schema(tags=TAGS, responses={(200, "image/png"): PNG, 404: ERRORS[404], 429: ERRORS[429]},
                   description="Link-preview image for a publicly verifiable certificate: no QR code, and the holder's "
                               "name only when they chose to show it. Same 404 as verification otherwise.")
    def get(self, request, verification_id):
        from .outputs import share_image
        row = verified_row(verification_id, request)
        response = HttpResponse(share_image(row), content_type="image/png")
        response["Cache-Control"] = "public, max-age=300"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Robots-Tag"] = "noindex"
        response["Referrer-Policy"] = "no-referrer"
        return response


class PublicShareCardView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [VerifyThrottle]

    @extend_schema(tags=TAGS, responses={(200, "text/html"): OpenApiResponse(OpenApiTypes.STR), 404: ERRORS[404], 429: ERRORS[429]},
                   description="Link-preview card for crawlers: Open Graph tags pointing at the share image and the "
                               "verification page. noindex; same 404 as verification.")
    def get(self, request, verification_id):
        from django.urls import reverse
        from apps.makerspaces.website_serving import PublicCard, share_response
        from .merge import kind_title
        from .rendering import verification_url
        row = verified_row(verification_id, request)
        image = request.build_absolute_uri(reverse("events-programme-public-certificate-share-image",
                                                   kwargs={"verification_id": row.serial}))
        title = f"{kind_title(row.kind)} · {row.event_title}"
        card = PublicCard(title=title, description=f"Issued by {row.issuer_name}. Check it on Space Works.",
                          url=verification_url(row), image_url=image, date=row.event_starts_at.date().isoformat(),
                          location="", availability="", audience_label="", revision=f"{row.pk}:{row.status}",
                          makerspace_name=row.issuer_name, image_alt=title)
        response = share_response(card)
        response["Referrer-Policy"] = "no-referrer"
        return response
