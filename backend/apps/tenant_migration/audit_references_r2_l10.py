"""Release-2 lane L10 audit meta ids (L11's backup, drill, move and station audits carry none).

Integration binding audits name the machine type, which travels with the space (remap).
An applied agent report names the device, the request and the printer job, all of which
travel; a refused one may name a request id the device merely sent, so that id stays
source provenance.
"""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

EDGES = {
    **{(f"devices.{action}", "machine_type_id"): AuditReference(R, "machines.MachineType")
       for action in ("integration_bound", "integration_updated", "integration_unbound")},
    ("machine_service.agent_report_applied", "device_id"): AuditReference(R, "devices.Device"),
    ("machine_service.agent_report_applied", "service_request_id"): AuditReference(R, "machines.MachineServiceRequest"),
    ("machine_service.agent_report_applied", "printer_job_id"): AuditReference(R, "devices.PrinterJob"),
    ("machine_service.agent_report_refused", "device_id"): AuditReference(R, "devices.Device"),
    ("machine_service.agent_report_refused", "service_request_id"): AuditReference(S, "machines.MachineServiceRequest"),
}
