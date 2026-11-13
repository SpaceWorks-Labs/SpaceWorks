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
    # Decision 312: device-adapter notices. Bodies carry the device only (no member, credential or machine detail).
    "adapter_attention": (
        gettext_noop("Machine needs attention: {{ device.name }}"),
        gettext_noop("The adapter {{ device.name }} ({{ device.id }}) reported that a machine needs attention.\n"
        "Open Devices in the staff console to see the event."),
    ),
    "adapter_runout": (
        gettext_noop("Material ran out: {{ device.name }}"),
        gettext_noop("The adapter {{ device.name }} ({{ device.id }}) reported that a consumable has run out."),
    ),
    "adapter_access_denied": (
        gettext_noop("Access denied at {{ device.name }}"),
        gettext_noop("A member was denied access at the device {{ device.name }} ({{ device.id }}).\n"
        "See the access log in the staff console for the reason."),
    ),
    "adapter_detection": (
        gettext_noop("Detection at {{ device.name }}"),
        gettext_noop("The adapter {{ device.name }} ({{ device.id }}) reported a detection (for example a print failure, "
        "smoke or a person) on a machine. Nothing was stopped automatically; open Devices in the staff console."),
    ),
    "adapter_job_review": (
        gettext_noop("Job report waiting for review: {{ device.name }}"),
        gettext_noop("The adapter {{ device.name }} ({{ device.id }}) reported a finished or failed job. It waits for "
        "staff review in Devices before the member is told the outcome."),
    ),
    "adapter_session_ending": (
        gettext_noop("Your machine session ends soon"),
        gettext_noop("Your session on a machine served by {{ device.name }} is about to reach its time limit."),
    ),
}
