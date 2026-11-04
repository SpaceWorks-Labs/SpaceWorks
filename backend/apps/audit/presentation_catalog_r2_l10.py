"""Release-2 lane L10: machine-integration bindings and agent job reports.

`devices.` and `machine_service.` are wrapper-site namespaces (actions written from a
parameter), so the dynamic policy denies their metadata at read time: these entries carry
labels only, and the raw audit row keeps its typed ids for auditors.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("devices.integration_bound", "Machine integration bound to a type"),
    P("devices.integration_updated", "Machine integration changed"),
    P("devices.integration_unbound", "Machine integration removed"),
    P("machine_service.agent_report_applied", "Printer report applied to a service job"),
    P("machine_service.agent_report_refused", "Printer report refused"),
)
