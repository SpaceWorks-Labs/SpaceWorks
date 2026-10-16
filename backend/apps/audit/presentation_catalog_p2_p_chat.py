"""Chat installation audit metadata contains neither provider IDs nor credentials."""
from .presentation_catalog_types import P

ENTRIES = (
    P("notification.chat_install_started", "Chat installation started", ("channel",)),
    P("notification.chat_install_state_consumed", "Chat installation proof consumed", ("channel",)),
)
