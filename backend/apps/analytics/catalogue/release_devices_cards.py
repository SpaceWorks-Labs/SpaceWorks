"""Analytics views (catalogue version 3): machine access grants, device adapters, card jobs, event certificates.

Release 0.12 (decision 327). Counts and timings only: people appear as member ids, and free text
(grant notes, command parameters, event data, recipient names, object keys) is left out on purpose.
"""

from .types import Col, View

VIEWS = (
    View("machine_access_grants", "machines",
         "Who may use which machine or machine type: one row per grant, kept after revocation.",
         "FROM {machines.MachineAccessGrant} g", "g.makerspace_id", (
             Col("grant_id", "g.id", "Grant id."),
             Col("member_id", "g.member_id", "Member who may use it (members)."),
             Col("machine_id", "g.machine_id", "One machine (machines), or empty for a whole type."),
             Col("machine_type_id", "g.machine_type_id", "Every machine of this type (machine_types)."),
             Col("source", "g.source", "Given by staff, or converted from a certification."),
             Col("granted_at", "g.granted_at", "Granted."),
             Col("expires_at", "g.expires_at", "Expires, if it does."),
             Col("revoked_at", "g.revoked_at", "Revoked."),
         ), since=3, requires=("machines",)),
    View("adapter_usage", "machines",
         "Sessions and jobs a device adapter reported: active and idle minutes and the outcome.",
         "FROM {devices.AdapterUsageLog} u", "u.makerspace_id", (
             Col("usage_id", "u.id", "Usage record id."),
             Col("device_id", "u.device_id", "Adapter device."),
             Col("started_at", "u.started_at", "Started."),
             Col("ended_at", "u.ended_at", "Ended."),
             Col("active_minutes", "u.active_minutes", "Minutes of use."),
             Col("idle_minutes", "u.idle_minutes", "Minutes idle."),
             Col("outcome", "u.outcome", "How it ended."),
             Col("error_code", "u.error_code", "Failure reason code, when it failed."),
         ), since=3, requires=("devices",)),
    View("adapter_access_decisions", "machines",
         "Every door or machine access decision an adapter made, with its reason code.",
         "FROM {devices.AdapterAccessLog} a", "a.makerspace_id", (
             Col("decision_id", "a.id", "Decision id."),
             Col("device_id", "a.device_id", "Adapter device."),
             Col("member_id", "a.member_id", "Member it concerned (members)."),
             Col("credential_type", "a.credential_type", "Kind of credential shown."),
             Col("allowed", "a.allowed", "Access was allowed."),
             Col("reason", "a.reason", "Reason code."),
             Col("offline", "a.offline", "Decided offline from the adapter's cache."),
             Col("created_at", "a.created_at", "Decided."),
         ), since=3, requires=("devices",)),
    View("card_jobs", "membership",
         "Card studio jobs: sheet printing, per-person PDFs, ZIPs, emails and wallet passes, with progress.",
         "FROM {card_designs.CardJob} j", "j.makerspace_id", (
             Col("job_id", "j.id", "Job id."),
             Col("kind", "j.kind", "What the job does."),
             Col("scope", "j.scope", "Which cards it covers."),
             Col("state", "j.state", "Queued, running, finished, failed or cancelled."),
             Col("total", "j.total", "Cards in the job."),
             Col("done", "j.done", "Cards finished."),
             Col("failed", "j.failed", "Cards that failed."),
             Col("created_at", "j.created_at", "Requested."),
             Col("finished_at", "j.finished_at", "Finished."),
         ), since=3, requires=("membership",)),
    View("event_certificates", "events",
         "Certificates issued for events: kind, state and revocation, never the recipient or the file.",
         "FROM {events.EventAttendanceCertificate} c JOIN {events.Event} e ON e.id = c.event_id",
         "e.makerspace_id", (
             Col("certificate_id", "c.id", "Certificate id."),
             Col("event_id", "c.event_id", "Event (events)."),
             Col("kind", "c.kind", "Attendance, participant, winner, thanks and so on."),
             Col("status", "c.status", "Render state."),
             Col("public_verification_enabled", "c.public_verification_enabled", "Anyone can verify it online."),
             Col("issued_at", "c.issued_at", "Issued."),
             Col("revoked_at", "c.revoked_at", "Revoked."),
         ), since=3, requires=("events",)),
)
