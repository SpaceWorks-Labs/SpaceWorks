from datetime import timedelta
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.audit.services import record
from apps.events import event_authority
from apps.events.event_permissions import EDIT_DETAILS
from apps.events.credentials.views import ERRORS
from apps.events.serializers_staff_tools import StrictSerializer
from apps.events.profile_photos.views import private
from apps.events.throttles import CredentialRenderThrottle
from .badge_designs import validate_design
from .layout import DESIGN_STOCK_CHOICES
from .serializers import BadgeDocumentSerializer
from .print_snapshot import BadgeSnapshot
from .layer_rendering import QrResource


class BadgePreviewSerializer(StrictSerializer):
    document = BadgeDocumentSerializer()
    stock = serializers.ChoiceField(choices=DESIGN_STOCK_CHOICES)


class BadgePreviewView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=["Event credentials"], request=BadgePreviewSerializer,
                   responses={(200, "application/pdf"): OpenApiTypes.BINARY, **ERRORS},
                   description="Fixed sample participant and nonresolving QR pattern. No credential or profile photo is read or issued.")
    def post(self, request, pk):
        from apps.events.badge_rendering import render_credential_badges_pdf
        event = event_authority.get_event(request.user, pk, EDIT_DETAILS)
        serializer = BadgePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        document = validate_design(values["document"], values["stock"])
        now = timezone.now()
        snapshot = BadgeSnapshot(registration_id=0, event_id=event.pk, member_id=None,
            authorized_fields=(("name", "Sample participant"), ("event", "Sample event"),
                               ("eventDate", "18 October 2026"), ("organisation", "Space Works"),
                               ("issueDate", "18 October 2026")),
            template_revision="preview", stock=values["stock"], logo_artwork_revision=None,
            credential_generation=None, credential_render_handle=0, presentation_id=None,
            presentation_version=None, source_profile_id=None, source_avatar_revision=None,
            photo_sha256=None, photo_render_handle=None, created_at=now, expires_at=now+timedelta(minutes=5))
        content = render_credential_badges_pdf(document, (snapshot,), resolver=lambda handle: QrResource("SAMPLE", dummy=True))
        # Preview is an audited action; it is never an issuance or attendance transition.
        record(request.user, "event.badge_design_previewed", makerspace=event.makerspace, target=event,
               meta={"stock": values["stock"]})
        response = private(HttpResponse(content, content_type="application/pdf"))
        response["Content-Disposition"] = 'attachment; filename="sample-event-badge.pdf"'
        return response
