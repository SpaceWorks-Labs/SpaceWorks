"""Release-2 lane L10: machine-integration bindings and agent job reports.

`devices.` and `machine_service.` are wrapper-site namespaces (actions written from a
parameter), so the dynamic policy denies their metadata at read time: these entries carry
labels only, and the raw audit row keeps its typed ids for auditors.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("devices.integration_bound", gettext_lazy("Machine integration bound to a type")),
    P("devices.integration_updated", gettext_lazy("Machine integration changed")),
    P("devices.integration_unbound", gettext_lazy("Machine integration removed")),
    P("machine_service.agent_report_applied", gettext_lazy("Printer report applied to a service job")),
    P("machine_service.agent_report_refused", gettext_lazy("Printer report refused")),
)
