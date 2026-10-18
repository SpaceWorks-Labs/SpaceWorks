"""R uses the Events boundary with the reimbursement module conjunction."""
from apps.events.staged_forms.transactions import (
    Context, changed, require_outer, command as event_command,
)


def command(**kwargs):
    kwargs.setdefault("reimbursement", True)
    return event_command(**kwargs)
