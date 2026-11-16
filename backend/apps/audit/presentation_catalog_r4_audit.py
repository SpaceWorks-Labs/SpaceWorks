"""R4 audit B: state changes that wrote no audit entry before (PRD section 11)."""

from django.utils.translation import gettext_noop

from .presentation_catalog_types import P

ENTRIES = (
    P("qr.asset_created", gettext_noop("Asset QR code created")),
    P("kiosk.station_session_ended", gettext_noop("Kiosk station session ended"), ("leases_revoked",)),
    P("managed_hosting.invoice_checkout_started", gettext_noop("Hosting invoice checkout opened"), ("provider",)),
    P("shop.receipt_emailed", gettext_noop("Shop receipt emailed"), ("guest_email_saved",)),
    P("account.merge_codes_resent", gettext_noop("Account link codes resent"), ("method", "resends")),
    P("card_design.font_requested", gettext_noop("Card font download requested"), ("family", "weights")),
    P("notification.read", gettext_noop("Notification marked read")),
    P("notification.read_all", gettext_noop("All notifications marked read"), ("updated",)),
    P("telegram.test_sent", gettext_noop("Telegram test alert sent")),
    # /control/ form edits (apps/audit/control_log.py): the model and field names, never values.
    P("control.object_added", gettext_noop("Record added in /control/"), ("via", "model")),
    P("control.object_changed", gettext_noop("Record changed in /control/"), ("via", "model", "changed_fields")),
    P("control.object_deleted", gettext_noop("Record deleted in /control/"), ("via", "model")),
    P("control.objects_deleted", gettext_noop("Records deleted in /control/"), ("via", "model", "count")),
)
