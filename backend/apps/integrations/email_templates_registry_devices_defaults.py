"""Staff-only device notification wording, with no machine or credential context."""
from django.utils.translation import gettext_noop

DEFAULTS = {
    "offline": (
        gettext_noop("Device offline: {{ device.name }}"),
        gettext_noop("Device {{ device.name }} ({{ device.kind }}, {{ device.id }}) is offline.\n"
        "Last seen: {{ device.last_seen_at }}\nOffline since: {{ device.offline_since }}"),
    ),
    "recovered": (
        gettext_noop("Device recovered: {{ device.name }}"),
        gettext_noop("Device {{ device.name }} ({{ device.kind }}, {{ device.id }}) has recovered.\n"
        "Last seen: {{ device.last_seen_at }}"),
    ),
}
