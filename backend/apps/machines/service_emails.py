"""Fail-safe notification seam for machine-service lifecycle events."""

from django.utils.translation import gettext
import logging

from apps.notifications.emit import emit_notification

logger = logging.getLogger(__name__)


def notify_service_status(service_request, event):
    """Emit a staff notification without allowing delivery to break the workflow."""
    try:
        from apps.machines.notifications_p2_service import notify_service
        from apps.machines.service_printing_emails import _is_printer_request, notify_printer_service_status
        if _is_printer_request(service_request):
            notify_printer_service_status(service_request, event)
        else:
            notify_service(service_request, event)
    except Exception:
        logger.exception("machine_printer_service_notification_failed", extra={"request_id": getattr(service_request, "pk", None), "event": event})
    try:
        makerspace = service_request.makerspace
        emit_notification(
            makerspace,
            event=f"machine_service.{event}",
            title=gettext("Machine service request updated"),
            body=(
                gettext('Machine service request #{pk} {event}. Status: {status}.').format(pk=service_request.pk, event=event, status=service_request.status)
            ),
            url_path=f"/admin/machine-service/requests/{service_request.pk}",
        )
    except Exception:
        logger.exception(
            "machine_service_notification_failed",
            extra={"request_id": getattr(service_request, "pk", None), "event": event},
        )
