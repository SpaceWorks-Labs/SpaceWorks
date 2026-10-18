"""Compatibility imports for the split source-gate policy catalogs."""

from .gate_policy_http import (
    WA_TWILIO_PARTICIPANTS,
    HTTP_EXEMPTIONS,
    HTTP_ANONYMOUS_EXEMPTIONS,
    HTTP_ANONYMOUS_PARTICIPANTS,
    ADMIN_ACTION_EXEMPTIONS,
)
from .gate_policy_tasks import (
    TASK_EXEMPTIONS,
    TASK_TENANT_RESOLVERS,
    TASK_INTERNAL_PARTICIPANTS,
    FANOUT_GATE_PARTICIPANTS,
)
from .gate_policy_replay import (
    REPLAY_HTTP_PARTICIPANTS,
    REPLAY_TASK_PARTICIPANTS,
    REPLAY_FANOUT_PARTICIPANTS,
)
from .gate_policy_objects import (
    LIFECYCLE_EXEMPTIONS,
    OBJECT_MUTATION_PARTICIPANTS,
)
from .gate_policy_public_pages import (
    TENANT_PAGE_ROUTES, GLOBAL_PAGE_ROUTES, PAGE_SERVICE_PARTICIPANTS,
)
