from .presentation_catalog_types import P

ENTRIES = (
    P("notification.whatsapp_callback_applied", "WhatsApp callback applied", ("kind", "state")),
    P("notification.whatsapp_proof_rejected", "WhatsApp account proof refused"),
    P("notification.whatsapp_templates_refreshed", "WhatsApp template approvals refreshed", ("changed", "unavailable")),
)
