"""Staff event detail and aggregate-count read contracts."""

from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.events.models import Event, EventRegistration
from apps.events.capacity import effective_registration_cutoff, registration_is_open
from apps.inventory import public_image_storage
from apps.makerspaces.platform import feature_enabled
from apps.events.serializers_public import EventOrganizerSummarySerializer
from .serializers_public_surface import PUBLIC_SURFACE_FIELDS, EventPublicSurfaceFields


class EventRegistrationCountsSerializer(serializers.Serializer):
    pending_approval = serializers.IntegerField(read_only=True)
    registered = serializers.IntegerField(read_only=True)
    waitlisted = serializers.IntegerField(read_only=True)
    rejected = serializers.IntegerField(read_only=True)
    cancelled = serializers.IntegerField(read_only=True)
    attended = serializers.IntegerField(read_only=True)


class EventAttendanceMarkSerializer(serializers.Serializer):
    source = serializers.ChoiceField(
        choices=("online", "qr"),
        default="online",
        required=False,
    )


from .serializers_event_authority import EventAuthorityFields
from .serializers_my_limit import EventMyLimitField


from .serializers_organization_audience import OrganizationAudienceFields


class EventAdminSerializer(EventPublicSurfaceFields, OrganizationAudienceFields, EventAuthorityFields, EventMyLimitField,
                           serializers.ModelSerializer):
    can_duplicate = serializers.SerializerMethodField(
        help_text="Whether the actor has tenant event-management authority to duplicate this event.",
    )
    badge_sensitive_fields_allowed = serializers.SerializerMethodField()
    broadcasts_enabled = serializers.SerializerMethodField()
    report_features = serializers.SerializerMethodField()
    ticketing_features = serializers.SerializerMethodField()
    makerspace_id = serializers.IntegerField(read_only=True)
    # Open items A19/A20: the venue's slug, so a cross-space drawer can load that space's switches.
    makerspace_slug = serializers.SerializerMethodField()
    created_by_id = serializers.IntegerField(allow_null=True, read_only=True)
    registration_counts = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    organizers = EventOrganizerSummarySerializer(many=True, read_only=True)
    audience_organizations = EventOrganizerSummarySerializer(many=True, read_only=True)
    effective_registration_cutoff_at = serializers.SerializerMethodField()
    registration_open = serializers.SerializerMethodField()
    series_summary = serializers.SerializerMethodField()
    offline_checkin_enabled = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField(
        help_text="Lowercase ISO code the space charges in; `payment_amount` is in this currency.")

    class Meta(OrganizationAudienceFields.Meta):
        model = Event
        fields = (
            'participating_organizations', 'audience_label', 'organization_admission_blocked',
            'id', 'staff_permissions', 'can_manage_staff', 'my_limit', 'can_duplicate',
            'makerspace_id', 'makerspace_slug', 'ticketing_features',
            'broadcasts_enabled', 'report_features', 'badge_sensitive_fields_allowed',
            'series_summary',
            'series_revision',
            'series_override_fields',
            'title',
            'description',
            'starts_at',
            'ends_at',
            'timezone_name', 'accent_preset',
            'location',
            'location_kind', 'venue_address', 'venue_map_url',
            'custom_form',
            'capacity',
            'payment_amount', 'currency',
            'registration_requires_approval',
            'registration_audience', 'category_id', 'tags',
            'cancellation_cutoff_hours',
            'registration_cutoff_at',
            'registration_cutoff_lead_minutes',
            'effective_registration_cutoff_at',
            'registration_open',
            'offline_checkin_enabled',
            'is_public',
            'show_registration_count',
            'image_url',
            'status',
            'created_by_id',
            'created_at',
            'updated_at',
            'registration_counts',
            'organizers',
            'audience_organizations',
            *PUBLIC_SURFACE_FIELDS,
        )
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_can_duplicate(self, obj):
        from apps.accounts import rbac
        if not self._authority(obj)[0]:
            return False
        actor = getattr(self.context.get("request"), "user", None)
        cache = self.context.setdefault("event_duplicate_authority", {})
        if obj.makerspace_id not in cache:
            cache[obj.makerspace_id] = rbac.can(actor, rbac.Action.MANAGE_EVENTS, obj.makerspace_id)
        return cache[obj.makerspace_id]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_ticketing_features(self, obj):
        return [key for key in ("events.invites", "events.ticket_types", "events.promo_codes", "events.organization_audience", "events.certificate_designer", "events.website", "events.embed", "events.online_delivery", "events.short_links",
                                     # Release 2 L6: paid ticketing v2 and venue fees.
                                     "events.orders", "events.addons", "events.transfers", "events.desk_collect",
                                     "events.refund_override", "events.venue_fees", "events.series_passes") if self._feature_enabled(obj, key)]

    def _feature_enabled(self, obj, key):
        flags = self.context.get("event_feature_flags", {}).get(obj.makerspace_id)
        if flags is not None and key in flags:
            return flags[key]
        return feature_enabled(obj.makerspace, key)

    @extend_schema_field(serializers.BooleanField())
    def get_badge_sensitive_fields_allowed(self, obj):
        # Mirrors services_badges.prepare_badges: event-scoped manage_registrations
        # (tenant managers receive every permission), no tenant VIEW_AUDIT.
        actor = getattr(self.context.get("request"), "user", None)
        _manager, permissions = self._authority(obj)
        return bool(actor and "manage_registrations" in permissions)

    def _report_allowed(self, actor, makerspace_id):
        # Event reports are keyed to MANAGE_EVENTS (the Event Manager's area action).
        from apps.accounts import rbac
        allowed = self.context.setdefault("event_report_allowed", {})
        if makerspace_id not in allowed:
            allowed[makerspace_id] = (
                rbac.can(actor, rbac.Action.MANAGE_EVENTS, makerspace_id)
                or rbac.can(actor, rbac.Action.VIEW_AUDIT, makerspace_id))
        return allowed[makerspace_id]

    @extend_schema_field(serializers.BooleanField())
    def get_broadcasts_enabled(self, obj):
        return self._feature_enabled(obj, "events.broadcasts")

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_report_features(self, obj):
        from apps.makerspaces.platform import module_enabled
        from . import event_authority
        actor = getattr(self.context.get("request"), "user", None)
        if not event_authority._active(actor):
            return []
        manager, permissions = self._authority(obj)
        if "manage_registrations" not in permissions:
            return []
        # Capability checks consult live restoration state. Cache them only for
        # this response, so a list checks each tenant rather than each event.
        modules = self.context.setdefault("event_report_modules", {})
        if obj.makerspace_id not in modules:
            modules[obj.makerspace_id] = module_enabled(obj.makerspace, "reports")
        if not modules[obj.makerspace_id]:
            return []
        # Decision 248 / EB1: a grantee (co-organizer) with manage_registrations on THIS event gets this event's
        # analytics and registration export; the report routes re-check the grant per event. The PDF stays
        # with the managers because its authority is the event manager's alone.
        tenant_reader = self._report_allowed(actor, obj.makerspace_id)
        if not tenant_reader and not manager:
            keys = ["analytics"]
            if self._feature_enabled(obj, "reports.event_exports"):
                keys.append("exports")
            return keys
        if not tenant_reader:
            return []
        keys = ["analytics"]
        if self._feature_enabled(obj, "reports.event_exports"):
            keys.append("exports")
        if manager and self._feature_enabled(obj, "reports.event_pdf"):
            keys.append("pdf")
        return keys

    # The raw object key is never exposed: staff and public both receive a resolved
    # URL, matching PublicMachineSerializer.
    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_image_url(self, obj):
        key = obj.image_key
        if obj.series_id and "image_key" not in (obj.series_override_fields or []):
            key = obj.series.image_key
        return public_image_storage.public_url(key) or None

    @extend_schema_field({
        'type': 'object', 'nullable': True,
        'properties': {
            'id': {'type': 'integer'}, 'public_token': {'type': 'string', 'format': 'uuid'},
            'title': {'type': 'string'}, 'timezone': {'type': 'string'},
        },
    })
    def get_series_summary(self, obj):
        if not obj.series_id:
            return None
        return {
            'id': obj.series_id,
            'public_token': obj.series.public_token,
            'title': obj.series.title,
            'timezone': obj.series.recurrence_timezone,
        }

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_effective_registration_cutoff_at(self, obj):
        return effective_registration_cutoff(obj)

    @extend_schema_field(serializers.BooleanField())
    def get_registration_open(self, obj):
        return registration_is_open(obj, timezone.now())

    @extend_schema_field(serializers.CharField())
    def get_makerspace_slug(self, obj) -> str:
        # One lookup per venue on a page, like the currency below.
        cache = self.context.setdefault("event_space_slug", {})
        if obj.makerspace_id not in cache:
            cache[obj.makerspace_id] = obj.makerspace.slug
        return cache[obj.makerspace_id]

    def get_currency(self, obj):
        from apps.payments.models import MakerspacePaymentSettings
        cache = self.context.setdefault("event_currency", {})
        if obj.makerspace_id not in cache:
            # Read through the venue's `payment_settings` relation so a list that select_related it
            # costs no query here; `for_makerspace` always issues a fresh one.
            from django.core.exceptions import ObjectDoesNotExist
            try:
                settings_row = obj.makerspace.payment_settings
            except ObjectDoesNotExist:
                settings_row = MakerspacePaymentSettings(makerspace=obj.makerspace)
            cache[obj.makerspace_id] = settings_row.default_currency
        return cache[obj.makerspace_id]

    @extend_schema_field(serializers.BooleanField())
    def get_offline_checkin_enabled(self, obj):
        return self._feature_enabled(obj, "events.offline_checkin")

    @extend_schema_field(EventRegistrationCountsSerializer)
    def get_registration_counts(self, obj):
        annotations = {
            status: getattr(obj, f'{status}_count', None)
            for status in EventRegistration.Status.values
        }
        if all(value is not None for value in annotations.values()):
            return annotations
        return obj.registrations.aggregate(
            **{
                status: Count('id', filter=Q(status=status))
                for status in EventRegistration.Status.values
            }
        )
