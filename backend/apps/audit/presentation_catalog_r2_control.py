"""Lane r2-control-restructure (#190): actions the web superadmin console now starts itself."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("backup.drill_requested", gettext_noop("Restore drill started from the console")),
    P("platform.oidc_provider_saved", gettext_noop("Single sign-on provider saved"), ("via", "created", "changed_fields")),
    P("chat_template.saved", gettext_noop("Chat template saved"), ("via", "feature", "event")),
    P("chat_template.deleted", gettext_noop("Chat template removed"), ("via", "feature", "event")),
)
