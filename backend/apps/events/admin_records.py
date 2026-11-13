"""/control/ "Events": events, series, registrations and ticket orders, read-only (0.12.0).

Events are created, published, cancelled and checked in through the events services in the
web console (row and module locks, quotas, the audit trail). Registrants' names, contact
details, answers and check-in tokens are never shown here.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.events.models_event import Event
from apps.events.models_orders import EventOrder
from apps.events.models_registration import EventRegistration
from apps.events.models_series import EventSeries
from config.admin_display import record_link, status_badge
from config.admin_records import ControlRecordAdmin


class EventRecordAdmin(ControlRecordAdmin):
    list_display = ("title", "makerspace", "starts_at", "ends_at", "status_label", "is_public", "capacity",
                    "payment_amount")
    list_filter = ("status", "is_public", "location_kind", "delivery_mode")
    search_fields = ("title", "makerspace__name", "makerspace__slug")
    list_select_related = ("makerspace",)
    ordering = ("-starts_at",)
    date_hierarchy = "starts_at"
    hidden_fields = ("join_url_encrypted", "public_token", "calendar_uid", "image_key")
    status_label = status_badge("status")


class EventSeriesRecordAdmin(ControlRecordAdmin):
    list_display = ("title", "makerspace", "recurrence_rule", "status_label", "is_public", "last_materialized_at")
    list_filter = ("status", "is_public")
    search_fields = ("title", "makerspace__name")
    list_select_related = ("makerspace",)
    ordering = ("-created_at",)
    hidden_fields = ("public_token", "calendar_uid", "image_key")
    status_label = status_badge("status")


class EventRegistrationRecordAdmin(ControlRecordAdmin):
    makerspace_lookup = "event__makerspace_id"
    list_display = ("id", "event_ref", "space", "status_label", "registration_audience", "is_crew", "created_at",
                    "cancelled_at")
    list_filter = ("status", "registration_audience", "is_crew")
    search_fields = ("event__title", "event__makerspace__name")
    list_select_related = ("event", "event__makerspace")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    hidden_fields = ("checkin_token", "email_hash_generation", "host_waiver")
    status_label = status_badge("status")

    @admin.display(description=_("Event"), ordering="event__title")
    def event_ref(self, obj):
        return obj.event.title

    @admin.display(description=_("Space"), ordering="event__makerspace__name")
    def space(self, obj):
        return obj.event.makerspace


class EventOrderRecordAdmin(ControlRecordAdmin):
    list_display = ("id", "makerspace", "event_ref", "kind", "status_label", "total", "currency", "created_at",
                    "paid_at")
    list_filter = ("status", "kind", "currency")
    search_fields = ("event__title", "makerspace__name")
    list_select_related = ("makerspace", "event")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    status_label = status_badge("status")

    @admin.display(description=_("Event"), ordering="event__title")
    def event_ref(self, obj):
        return obj.event.title if obj.event_id else record_link(obj, "series", _("Series #%(id)s"),
                                                                 "admin:events_eventseries_change")
