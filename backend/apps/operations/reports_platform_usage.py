"""Counts-only platform activity; every tenant measurement retains its makerspace."""

from datetime import datetime, time, timezone as datetime_timezone
from decimal import Decimal

from django.db.models import DateTimeField
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.models_activity import DeviceActivityDay
from apps.accounts.models_devices import NativeAppRegistration
from apps.bookings.models import Booking
from apps.devices.models import Device
from apps.integrations.models_push import PushDevice
from apps.events.models import EventRegistration
from apps.hardware_requests.models import HardwareRequestItem
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.module_registry import MODULES, module_available
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import servable_queryset
from apps.machines import role_scope
from apps.machines.models import MachineServiceRequest, MachineUsageEntry
from apps.operations.platform_scope import platform_analytics_spaces, require_platform_context
from apps.operations.report_types import ReportNotFound, ReportResult
from apps.operations.reports_common import apply_range, limited
from apps.operations.reports_finance_sources import finance_sources
from apps.operations.reports_j_common import calendar_range, period
from apps.operations.reports_platform_consumables import consumption_rows, cost_rows
from apps.operations.report_fields_j import USAGE_FIELDS as FIELDS



def _in_window(at, date_range):
    return at is not None and (not date_range or ((date_range[0] is None or at >= date_range[0]) and (date_range[1] is None or at < date_range[1])))


def build_platform_usage(makerspace_id=None, *, platform_context=None, limit=None, date_range=None, grain="day"):
    ctx = require_platform_context(platform_context)
    date_range = calendar_range(date_range)
    if makerspace_id is not None:
        raise ReportNotFound()
    spaces = list(servable_queryset(platform_analytics_spaces(ctx)).order_by("pk"))
    groups = {}

    def add(space_id, at, metric, value=1, *, entity_kind="makerspace", entity_id=None, unit="count", currency=None):
        if unit not in ("count", "items", "hours", "grams", "milliliters", "millimeters", "currency", "minor_currency", "minutes"):
            unit = "unknown"
        key = (space_id, period(at, grain), metric, entity_kind, str(entity_id) if entity_id is not None else None, unit, currency)
        groups[key] = groups.get(key, 0) + value

    now = timezone.now()
    for row in apply_range(NativeAppRegistration.objects.filter(makerspace__isnull=True), "created_at", date_range).values("created_at", "platform", "status").iterator():
        add(None, row["created_at"], "app_registrations", entity_kind="platform_status", entity_id=f"{row['platform']}:{row['status']}")
    for space in spaces:
        if _in_window(space.created_at, date_range):
            add(space.pk, space.created_at, "makerspace_growth")
        for module in MODULES:
            if module_enabled(space, module.key) and module_available(module.key):
                add(space.pk, now, "module_adoption", entity_kind="module", entity_id=module.key)
        if module_enabled(space, "member_accounts") or module_enabled(space, "membership"):
            members = apply_range(MakerspaceMembership.objects.filter(makerspace=space), "created_at", date_range)
            for at in members.values_list("created_at", flat=True).iterator():
                add(space.pk, at, "member_growth")
        if any(module_enabled(space, key) for key in ("request_workflow", "guest_handover", "public_inventory")):
            items = HardwareRequestItem.objects.filter(request__makerspace=space, issued_quantity__gt=0)
            items = apply_range(items, "request__issued_at", date_range)
            loans = set()
            for row in items.values("request_id", "request__issued_at", "product_id", "issued_quantity").iterator():
                if row["request__issued_at"] is None:
                    continue
                add(space.pk, row["request__issued_at"], "borrowed_hardware", row["issued_quantity"], entity_kind="product", entity_id=row["product_id"], unit="items")
                if row["request_id"] not in loans:
                    add(space.pk, row["request__issued_at"], "loans")
                    loans.add(row["request_id"])
        if module_enabled(space, "bookings"):
            bookings = apply_range(Booking.objects.filter(space__makerspace=space, status__in=("confirmed", "completed", "no_show")), "starts_at", date_range)
            for row in bookings.values("starts_at", "ends_at", "space_id", "space__machine_type_id").iterator():
                add(space.pk, row["starts_at"], "bookings")
                if (row["space__machine_type_id"] and module_enabled(space, "machines")
                        and role_scope.scope_covers_type(role_scope.manage_scope_for(ctx.actor, space.pk), row["space__machine_type_id"])):
                    add(space.pk, row["starts_at"], "booked_machine_hours", Decimal(str((row["ends_at"] - row["starts_at"]).total_seconds())) / 3600,
                        entity_kind="machine_type", entity_id=row["space__machine_type_id"], unit="hours")
        if module_enabled(space, "events"):
            registrations = apply_range(EventRegistration.objects.filter(event__makerspace=space).exclude(status__in=("cancelled", "rejected")), "created_at", date_range)
            for row in registrations.values("created_at", "event_id").iterator():
                add(space.pk, row["created_at"], "event_registrations", entity_kind="event", entity_id=row["event_id"])
        # Financial history remains core even when the online rail is absent.
        for _space, row in finance_sources(space.pk, date_range=date_range):
            if row["effective"] and row.get("collected_amount", 0):
                add(space.pk, row["date"], "revenue", row["collected_amount"], unit="currency", currency=row["currency"])
            if row["effective"] and row.get("refunded_amount", 0):
                add(space.pk, row["date"], "refunds", row["refunded_amount"], unit="currency", currency=row["currency"])
        if module_enabled(space, "machines"):
            scope = role_scope.manage_scope_for(ctx.actor, space.pk)
            manual = MachineUsageEntry.objects.filter(machine__makerspace=space).filter(role_scope.scope_q_for(
                scope, machine_id_paths=("machine_id",), type_id_paths=("machine__machine_type_id",)))
            # created_at uses PreservableCreatedAtField; declare the shared SQL type.
            manual = manual.annotate(at=Coalesce("started_at", "created_at", output_field=DateTimeField()))
            manual = apply_range(manual, "at", date_range)
            for row in manual.values("at", "machine_id", "hours").iterator():
                add(space.pk, row["at"], "manual_machine_hours", row["hours"], entity_kind="machine", entity_id=row["machine_id"], unit="hours")
            if module_enabled(space, "machine_service"):
                services = MachineServiceRequest.objects.filter(makerspace=space, status__in=("completed", "collected", "failed"))
                services = role_scope.scoped_service_requests(ctx.actor, services, [space.pk])
                services = services.annotate(at=Coalesce("completed_at", "failed_at"), machine=Coalesce("assigned_machine_id", "bucket__machine_id"))
                for row in apply_range(services, "at", date_range).values("at", "machine", "actual_minutes", "estimated_minutes", "fail_percent_complete", "status").iterator():
                    if row["at"]:
                        minutes = Decimal(row["estimated_minutes"]) * row["fail_percent_complete"] / 100 if row["status"] == "failed" else Decimal(row["actual_minutes"])
                        add(space.pk, row["at"], "service_machine_hours", minutes / 60,
                            entity_kind="machine" if row["machine"] else "unattributed", entity_id=row["machine"], unit="hours")
                for row in consumption_rows(space, date_range, actor=ctx.actor):
                    add(space.pk, row["at"], "consumables", row["quantity"], entity_kind=row["entity_kind"], entity_id=row["entity_id"], unit=row["unit"])
                for row in cost_rows(space, date_range, actor=ctx.actor):
                    add(space.pk, row["recorded_at"], "consumable_cost", row["cost_total_minor"], entity_kind="cost_source", entity_id=row["source_kind"], unit="minor_currency", currency=row["currency"])
        if module_enabled(space, "devices"):
            for row in apply_range(Device.objects.filter(makerspace=space), "created_at", date_range).values("created_at", "kind").iterator():
                add(space.pk, row["created_at"], "device_adoption", entity_kind="device_kind", entity_id=row["kind"])
        if module_enabled(space, "mobile"):
            for row in apply_range(NativeAppRegistration.objects.filter(makerspace=space), "created_at", date_range).values("created_at", "platform", "status").iterator():
                add(space.pk, row["created_at"], "app_registrations", entity_kind="platform_status", entity_id=f"{row['platform']}:{row['status']}")
            push = apply_range(PushDevice.objects.filter(makerspace=space), "created_at", date_range)
            for row in push.values("created_at", "provider", "environment").iterator():
                add(space.pk, row["created_at"], "push_device_registrations", entity_kind="provider_environment", entity_id=f"{row['provider']}:{row['environment']}")
    visible_mobile = [s.pk for s in spaces if module_enabled(s, "mobile")]
    from django.db.models import Q
    activity = DeviceActivityDay.objects.filter(Q(makerspace_id__in=visible_mobile) | Q(makerspace__isnull=True))
    if date_range:
        if date_range[0]:
            activity = activity.filter(local_day__gte=date_range[0].date())
        if date_range[1]:
            activity = activity.filter(local_day__lt=date_range[1].date())
    # Deduplicate grants across visible tenants and unselected (NULL) requests.
    # Assign the daily count to its first visible tenant, falling back to NULL for
    # deployment-only activity; no identifier leaves this private calculation.
    grants = {}
    for row in activity.order_by("local_day", "makerspace_id").values("local_day", "platform", "grant_id", "makerspace_id").iterator():
        grants.setdefault((row["local_day"], row["platform"], row["grant_id"]), row["makerspace_id"])
    for (day, platform, _grant), space_id in grants.items():
        add(space_id, datetime.combine(day, time.min, tzinfo=datetime_timezone.utc), "active_app_sessions",
            entity_kind="platform", entity_id=platform)
    rows = [dict(zip(FIELDS, (*key, value), strict=True)) for key, value in groups.items()]
    rows.sort(key=lambda r: (r["metric"], r["unit"], r["currency"] or "", -r["value"], r["makerspace_id"] or 0, r["entity_id"] or "", r["period"]))
    return ReportResult(FIELDS, limited(rows, limit), {"definition": "UTC periods; activity counts remain per makerspace. Machine service, manual and booked hours are separate measures. Adoption is a current snapshot; growth uses creation time.",
                                                     "limitations": "Active app sessions count grants once per recorded local day across visible/NULL attribution; hidden rows are excluded. Daily counts roll up as active session-days. Missing consumable costs are unknown. Units and currencies never combine."})
