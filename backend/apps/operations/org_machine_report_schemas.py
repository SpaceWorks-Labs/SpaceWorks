"""Organization schema parity without a registry/registration import cycle."""

from .org_machine_reports import SERVICE_GROUPS, USAGE_GROUPS
from .reports_machine_downtime import FIELDS as DOWNTIME_FIELDS
from .reports_machine_health import ERROR_FIELDS, PRINTER_FIELDS, WARRANTY_FIELDS
from .reports_machine_maintenance_v2 import FIELDS as MAINTENANCE_FIELDS
from .reports_machine_service_v2 import FIELDS as SERVICE_FIELDS
from .reports_machine_usage_v2 import FIELDS as USAGE_FIELDS

MACHINE_ORG_FIELDS = {
    "machine-usage": USAGE_FIELDS,
    "machine-downtime": DOWNTIME_FIELDS,
    "maintenance-activity": MAINTENANCE_FIELDS,
    "machine-service": SERVICE_FIELDS,
    "printer-jobs": PRINTER_FIELDS,
    "machine-errors": ERROR_FIELDS,
    "warranty-expiry": WARRANTY_FIELDS,
}
MACHINE_ORG_GROUPS = {
    "machine-usage": USAGE_GROUPS,
    "machine-downtime": ("period", "machine_id", "status"),
    "maintenance-activity": ("period", "machine_id"),
    "machine-service": SERVICE_GROUPS,
    "printer-jobs": ("period", "machine_id", "state", "outcome"),
    "machine-errors": ("period", "machine_id", "severity"),
    "warranty-expiry": ("warranty_id",),
}
