"""Per-event card settings (approval at event level, #136; the first-aid extras switch,
Q-I5), the first-aid list itself, and the registrant's own ticket download (X49)."""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.openapi_errors import errors

from .id_cards_views import organiser_event
from .models import EventCardSettings, EventRegistration

TAGS = ["Event ID cards"]


def _approval_required(event):
    from apps.card_designs.models import CardApprovalSetting
    row = CardApprovalSetting.objects.filter(event=event, group="event").first()
    return row.required if row else None


class EventCardSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="This event's card settings", request=None,
                   responses={200: OpenApiTypes.OBJECT, **errors(401, 403, 404)})
    def get(self, request, pk):
        event = organiser_event(request.user, pk)
        row = EventCardSettings.objects.filter(event=event).first()
        return Response({"extras_visible_to_organizers": bool(row and row.extras_visible_to_organizers),
                         "design_approval_required": _approval_required(event)})

    @extend_schema(tags=TAGS, summary="Change this event's card settings (event settings authority)",
                   request=OpenApiTypes.OBJECT, responses={200: OpenApiTypes.OBJECT, **errors(400, 401, 403, 404)})
    def put(self, request, pk):
        from apps.card_designs.approval import set_level
        from apps.makerspaces.settings_authority import assert_setting_write
        event = organiser_event(request.user, pk)
        extras = request.data.get("extras_visible_to_organizers")
        approval = request.data.get("design_approval_required")
        if extras is not None:
            if type(extras) is not bool:
                raise ValidationError({"extras_visible_to_organizers": "Use true or false."})
            row, _ = EventCardSettings.objects.get_or_create(event=event)
            if row.extras_visible_to_organizers != extras:
                row.extras_visible_to_organizers = extras
                row.save(update_fields=["extras_visible_to_organizers", "updated_at"])
                audit.record(request.user, "event_card.extras_access_changed", makerspace=event.makerspace,
                             target=row, meta={"event_id": event.pk, "enabled": extras})
        if approval is not None:
            if type(approval) is not bool:
                raise ValidationError({"design_approval_required": "Use true or false."})
            assert_setting_write(request.user, event.makerspace, "events", "card_designs.approval")
            set_level(request.user, event.makerspace, "event", approval, event=event)
        return self.get(request, pk)


class EventCardExtrasView(APIView):
    """Q-I5 exception: organisers read first-aid extras only when this event switched it on."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="First-aid extras of this event's card holders (when switched on)", request=None,
                   responses={200: OpenApiTypes.OBJECT, **errors(401, 403, 404)})
    def get(self, request, pk):
        from apps.accounts.pii_presentation import require_pii_access
        from apps.card_designs.models import CardHolderExtras
        event = organiser_event(request.user, pk)
        if not EventCardSettings.objects.filter(event=event, extras_visible_to_organizers=True).exists():
            raise NotFound()
        require_pii_access(request.user, event.makerspace_id)
        rows = CardHolderExtras.objects.filter(event_card__event=event, consent_at__isnull=False).select_related(
            "event_card")
        audit.record(request.user, "event_card.extras_viewed", makerspace=event.makerspace, target=event,
                     meta={"event_id": event.pk, "count": rows.count()})
        response = Response([{"card_id": row.event_card_id, "name": row.event_card.printed_name,
                              "blood_group": row.blood_group, "emergency_contact_name": row.emergency_contact_name,
                              "emergency_contact_phone": row.emergency_contact_phone} for row in rows])
        response["Cache-Control"] = "private, no-store"
        return response


class MyTicketView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["My cards"], summary="My ticket for a registration (PDF or PNG)", request=None,
                   parameters=[OpenApiParameter("format", str, enum=["pdf", "png"])],
                   responses={(200, "application/pdf"): OpenApiTypes.BINARY, **errors(401, 404)})
    def get(self, request, pk):
        from .id_cards_tickets import render_ticket
        registration = get_object_or_404(EventRegistration.objects.select_related("event__makerspace"), pk=pk,
                                         member=request.user, status__in=("registered", "attended"))
        filename, data, content_type = render_ticket(registration, fmt=request.query_params.get("format", "pdf"))
        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        response["Cache-Control"] = "private, no-store"
        return response
