"""Chat installation audit metadata contains neither provider IDs nor credentials."""
from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("notification.chat_install_started", gettext_noop("Chat installation started"), ("channel",)),
    P("notification.chat_install_state_consumed", gettext_noop("Chat installation proof consumed"), ("channel",)),
)
