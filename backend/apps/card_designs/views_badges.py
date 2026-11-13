"""Badge designer routes (E-B1): the event's badge designs, role variants, design files, convert.

Authority is the design's own (`authority.require_edit`: the event's edit permission), never a new action;
every route 404s while `events.badge_designer` (role variants: `events.role_badges`) is off for the space.
"""
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.openapi_errors import errors

from . import badge_format, badge_import, designs, resolution, resolution_roles
from .authority import design_for, require_edit
from .badge_source import without_source
from .models import CardDesign
from .serializers import CardDesignSerializer
from .serializers_badges import (BadgeDesignResultSerializer, BadgeDesignsSerializer, BadgeFileSerializer,
                                 BadgeImportRequestSerializer, BadgeImportResultSerializer, BadgeRoleStartSerializer)
from .switches import badge_designer_on, role_badges_on

TAGS = ["Event badges"]
ATTENDEE = "attendee"


def _event(actor, pk):
    from apps.events.id_cards_views import organiser_event
    event = organiser_event(actor, pk)
    if not badge_designer_on(event.makerspace):
        raise NotFound()
    return event


def _organisation(event):
    from apps.events.organizer_models import EventOrganizer
    row = EventOrganizer.objects.filter(event=event).select_related("organization").order_by("pk").first()
    return row.organization if row else None


def _organisation_name(event):
    organisation = _organisation(event)
    return organisation.name if organisation else event.makerspace.name


def _document(settings, makerspace_id):
    return designs.validated(makerspace_id, {"version": 2, "source": {"format": "badge_v1", "settings": settings}},
                             check_contrast=False, domain="event_card")


def _form_fields(event):
    """The registration questions a badge may print (newest form revision), then the Team and Role lines."""
    from apps.events.models import EventFormRevision
    row = EventFormRevision.objects.filter(event=event, form_key="registration").order_by("-revision").first()
    schema = row.schema if row else None
    questions = (schema.get("questions") or schema.get("fields")) if isinstance(schema, dict) else schema
    fields = [{"key": f"registration:{item['key']}", "label": str(item.get("label") or item["key"])[:80]}
              for item in questions or () if isinstance(item, dict) and item.get("key") and not item.get("sensitive")]
    return fields + [{"key": badge_format.TEAM_FIELD_KEY, "label": gettext("Team")},
                     {"key": badge_format.CREW_KIND_FIELD_KEY, "label": gettext("Role")}]


def _format(row):
    return "none" if row is None else "badge_v1" if row.document.get("source") else "free_canvas"


def _event_designs(event):
    return CardDesign.objects.filter(event=event, domain="event_card", ticket_type__isnull=True, archived_at__isnull=True)


class EventBadgeDesignsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="This event's badge designs, per role, and what the designer may offer",
                   request=None, responses={200: BadgeDesignsSerializer, **errors(401, 403, 404)})
    def get(self, request, pk):
        from apps.events.contributions.models_roles import EventSponsor
        event = _event(request.user, pk)
        organisation = _organisation(event)
        rows = {row.card_role: row for row in _event_designs(event)}
        roles = [{"role": role or ATTENDEE, "design_id": rows[role].pk if role in rows else None,
                  "format": _format(rows.get(role)), "published": bool(role in rows and rows[role].published_document)}
                 for role in (None, *resolution_roles.ROLES)]
        sponsors = EventSponsor.objects.filter(event=event, active=True).exclude(logo_reference="").count()
        return Response({
            "event_id": event.pk, "event_title": event.title, "organisation_name": _organisation_name(event),
            "role_badges": role_badges_on(event.makerspace), "roles": roles, "fields": _form_fields(event),
            "max_print_fields": badge_format.PRINT_FIELD_MAX, "sponsor_limit_max": badge_format.SPONSOR_LIMIT_MAX,
            "presets": list(badge_format.PRESETS), "templates": list(badge_format.geo.TEMPLATES),
            "branding": {"has_organisation_logo": bool(organisation and organisation.logo_key),
                         "has_event_logo": bool(event.image_key), "sponsor_count": sponsors}})


class EventBadgeDesignRoleView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Open (or start) the badge design for a role",
                   description="`attendee` is the design every role uses and is started as a badge on first use. Any "
                               "other role needs `events.role_badges` and starts as a copy of the attendee badge with "
                               "its own label. `restart` replaces the draft with a fresh badge design.",
                   request=BadgeRoleStartSerializer,
                   responses={200: BadgeDesignResultSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk, role):
        event = _event(request.user, pk)
        if role != ATTENDEE and (role not in resolution_roles.ROLES or not role_badges_on(event.makerspace)):
            raise NotFound()
        data = BadgeRoleStartSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        defaults = badge_format.default_settings(event.title, _organisation_name(event))
        if role == ATTENDEE:
            row, created = resolution.get_or_create(event.makerspace, "event_card", actor=request.user, event=event)
            fresh = {**defaults}
        else:
            base = _event_designs(event).filter(card_role__isnull=True).first()
            seed = ((base.document.get("source") or {}).get("settings") if base else None) or defaults
            fresh = {**defaults, "badgeLabel": role.upper()}
            row, created = resolution_roles.get_or_create_variant(
                event, role, document=_document({**seed, "badgeLabel": role.upper()}, event.makerspace_id),
                actor=request.user)
        if data.validated_data["restart"] or (created and role == ATTENDEE):
            row = designs.save(request.user, row, _document(fresh, event.makerspace_id), expected_revision=row.revision)
        row.refresh_from_db()
        return Response({"design": CardDesignSerializer(row, context={"request": request}).data, "created": created})


def _badge_design(request, pk):
    design = require_edit(request.user, design_for(request.user, pk))
    if design.domain != "event_card" or not badge_designer_on(design.makerspace):
        raise NotFound()
    return design


def _settings(design):
    source = design.document.get("source")
    if not source:
        raise ValidationError({"source": gettext("This design is a free canvas, not a badge design.")},
                              code="not_a_badge_design")
    return source["settings"]


class CardDesignBadgeExportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Download the badge design file (JSON)", request=None,
                   responses={(200, "application/json"): BadgeFileSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, pk):
        design = _badge_design(request, pk)
        audit.record(request.user, "card_design.exported", makerspace=design.makerspace, target=design,
                     meta={"design_id": design.pk})
        response = Response(badge_import.export(_settings(design)))
        response["Content-Disposition"] = 'attachment; filename="badge-design.json"'
        return response


class CardDesignBadgeImportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Import a badge design file into this design's draft",
                   description="Accepts `spaceworks-event-badge` v1 and the SpaceWorks-Events kinds "
                               "`swe-id-card-design` / `yuyu-id-card-design` as written. Never trusted: normalised, "
                               "unknown keys dropped, and `notes` list what did not survive.",
                   request=BadgeImportRequestSerializer,
                   responses={200: BadgeImportResultSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        design = _badge_design(request, pk)
        data = BadgeImportRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        event = design.event
        settings, notes = badge_import.parse(
            data.validated_data["file"], event_title=event.title if event else "",
            organisation_name=_organisation_name(event) if event else design.makerspace.name)
        design = designs.save(request.user, design, _document(settings, design.makerspace_id),
                              expected_revision=design.revision)
        audit.record(request.user, "card_design.imported", makerspace=design.makerspace, target=design,
                     meta={"design_id": design.pk})
        known = {field["key"] for field in _form_fields(event)} if event else set()
        unmatched = [key for key in settings["printFieldKeys"] if key not in known and f"registration:{key}" not in known]
        design.refresh_from_db()
        return Response({"design": CardDesignSerializer(design, context={"request": request}).data, "notes": notes,
                         "unmatched_fields": unmatched})


class CardDesignBadgeConvertView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Convert a badge design to a free canvas (one way)",
                   description="Drops the structured source and keeps the compiled layers, which can then be edited "
                               "freely in the card designer. The badge designer can no longer open it; start a new "
                               "badge design to go back.",
                   request=None, responses={200: CardDesignSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        design = _badge_design(request, pk)
        _settings(design)
        design = designs.save(request.user, design, without_source(design.document), expected_revision=design.revision,
                              unlock=True)
        audit.record(request.user, "card_design.badge_converted", makerspace=design.makerspace, target=design,
                     meta={"design_id": design.pk, "domain": design.domain})
        design.refresh_from_db()
        return Response(CardDesignSerializer(design, context={"request": request}).data)
