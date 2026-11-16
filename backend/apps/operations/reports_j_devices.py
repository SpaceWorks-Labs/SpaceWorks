"""Device availability is observed status history, never inferred from audit text."""

from collections import defaultdict
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count, Sum
from django.utils import timezone

from apps.devices.models import Device, DeviceCommand, DeviceEvent, LabelPrintCommand
from apps.makerspaces.platform import module_enabled
from apps.operations.reports_common import apply_range, period_expression
from apps.operations.reports_j_common import area_spaces, calendar_range, period, rate, result
from apps.operations.report_fields_j import DEVICE_FIELDS as FIELDS, DEVICE_SUM_FIELDS as SUM_FIELDS



def _segments(start, end, grain, space):
    zone = ZoneInfo(space.timezone)
    while start < end:
        local = start.astimezone(zone)
        if grain == "month":
            next_day = local.date().replace(day=28) + timedelta(days=4)
            next_day = next_day.replace(day=1)
        else:
            next_day = local.date() + timedelta(days=(7 - local.weekday()) if grain == "week" else 1)
        stop = min(end, datetime.combine(next_day, time.min, tzinfo=zone))
        yield period(start, grain, space), stop.timestamp() - start.timestamp()
        start = stop


def build_device_health(makerspace_id, *, limit=None, date_range=None, grain="day"):
    now, records = timezone.now(), []
    for space in area_spaces(makerspace_id, "devices"):
        window = calendar_range(date_range, space)
        groups = defaultdict(lambda: {field: 0 for field in SUM_FIELDS})
        history = defaultdict(list)
        report_end = min(now, window[1]) if window and window[1] else now
        events = DeviceEvent.objects.filter(makerspace=space, created_at__lt=report_end,
                                           event_type__in=("enrolled", "offline_detected", "recovered")).order_by("device_id", "created_at", "pk")
        for event in events.values("device_id", "created_at", "event_type").iterator():
            history[event["device_id"]].append(event)
        devices = Device.objects.filter(makerspace=space).values("pk", "created_at", "revoked_at")
        for device in devices.iterator():
            start = max(device["created_at"], window[0]) if window and window[0] else device["created_at"]
            end = min(now, device["revoked_at"] or now, window[1] if window and window[1] else now)
            state = "unknown"
            cursor = start
            for event in history[device["pk"]]:
                if event["created_at"] < start:
                    state = "offline" if event["event_type"] == "offline_detected" else "online"
                    continue
                if event["created_at"] >= end:
                    break
                for bucket, seconds in _segments(cursor, event["created_at"], grain, space):
                    groups[(str(device["pk"]), bucket)][f"{state}_seconds"] += seconds
                state = "offline" if event["event_type"] == "offline_detected" else "online"
                if state == "offline":
                    groups[(str(device["pk"]), period(event["created_at"], grain, space))]["offline_incidents"] += 1
                cursor = event["created_at"]
            for bucket, seconds in _segments(cursor, end, grain, space):
                groups[(str(device["pk"]), bucket)][f"{state}_seconds"] += seconds
        commands = apply_range(DeviceCommand.objects.filter(makerspace=space, device__makerspace=space), "created_at", window)
        for row in commands.order_by().annotate(period=period_expression("created_at", grain, makerspace=space)).values("device_id", "period", "status").annotate(count=Count("pk")):
            state = groups[(str(row["device_id"]), row["period"].date().isoformat())]
            state["commands"] += row["count"]
            if row["status"] == "acknowledged":
                state["commands_acknowledged"] += row["count"]
            elif row["status"] == "delivery_failed":
                state["commands_failed"] += row["count"]
        if module_enabled(space, "qr_print_batches"):
            labels = apply_range(LabelPrintCommand.objects.filter(makerspace=space, device__makerspace=space), "created_at", window)
            for row in labels.order_by().annotate(period=period_expression("created_at", grain, makerspace=space)).values("device_id", "period", "result").annotate(count=Count("pk"), labels=Sum("item_count_snapshot")):
                state = groups[(str(row["device_id"]), row["period"].date().isoformat())]
                if row["result"] == "succeeded":
                    state["label_prints"] += row["count"]
                    state["labels_printed"] += row["labels"]
                elif row["result"] == "failed":
                    state["label_failures"] += row["count"]
        for (device_id, bucket), row in sorted(groups.items()):
            records.append({"makerspace_id": space.pk, "period": bucket, "device_id": device_id, **row,
                            "uptime_percent": rate(row["online_seconds"], row["online_seconds"] + row["offline_seconds"]),
                            "command_success_percent": rate(row["commands_acknowledged"], row["commands_acknowledged"] + row["commands_failed"])})
    return result(FIELDS, records, makerspace_id, limit, history="Availability is unknown until an enrollment/offline/recovery event; command success uses terminal deliveries only.")
