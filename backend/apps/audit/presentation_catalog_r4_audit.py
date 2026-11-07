"""R4 audit B: state changes that wrote no audit entry before (PRD section 11)."""

from .presentation_catalog_types import P

ENTRIES = (
    P("qr.asset_created", "Asset QR code created"),
    P("kiosk.station_session_ended", "Kiosk station session ended", ("leases_revoked",)),
    P("managed_hosting.invoice_checkout_started", "Hosting invoice checkout opened", ("provider",)),
    P("shop.receipt_emailed", "Shop receipt emailed", ("guest_email_saved",)),
    P("account.merge_codes_resent", "Account link codes resent", ("method", "resends")),
    P("card_design.font_requested", "Card font download requested", ("family", "weights")),
    P("notification.read", "Notification marked read"),
    P("notification.read_all", "All notifications marked read", ("updated",)),
    P("telegram.test_sent", "Telegram test alert sent"),
    # /control/ form edits (apps/audit/control_log.py): the model and field names, never values.
    P("control.object_added", "Record added in /control/", ("via", "model")),
    P("control.object_changed", "Record changed in /control/", ("via", "model", "changed_fields")),
    P("control.object_deleted", "Record deleted in /control/", ("via", "model")),
    P("control.objects_deleted", "Records deleted in /control/", ("via", "model", "count")),
)
