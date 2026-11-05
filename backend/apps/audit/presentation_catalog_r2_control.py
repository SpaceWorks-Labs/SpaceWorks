"""Lane r2-control-restructure (#190): actions the web superadmin console now starts itself."""

from .presentation_catalog_types import P

ENTRIES = (
    P("backup.drill_requested", "Restore drill started from the console"),
    P("platform.oidc_provider_saved", "Single sign-on provider saved", ("via", "created", "changed_fields")),
    P("chat_template.saved", "Chat template saved", ("via", "feature", "event")),
    P("chat_template.deleted", "Chat template removed", ("via", "feature", "event")),
)
