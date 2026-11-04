"""Release-2 lane L12 (machines and loans depth): literal export classification.

Every L12 row is the space's own operational record and exports with the space:

* vendors (a supplier's business contact, the same class of data as the existing
  `Warranty.vendor_contact`), and the To-Buy / warranty links to them;
* loan pickup timing and the waitlist (a member's place in line names that member, a
  relational account reference);
* the consumable flag, the public expected-back opt-in, a request's pickup window;
* the machine job flow (#140-#142): queue order, quotes (a frozen L15 quote: prices and
  rule ids only), failure outcome, pickup code and place, and the collector's name
  (encrypted personal data, like the requester's name), per-type job settings, batch runs;
* the downtime ledger, work orders and maintenance lockout, and machine time booking.
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
    "procurement.Vendor": "id makerspace name contact_name email phone website notes is_archived created_by "
                          "created_at updated_at",
    "hardware_requests.LoanReservationPolicy": "id makerspace pickup_window_hours reservation_max_days_ahead "
                                               "waitlist_offer_hours updated_at",
    "hardware_requests.LoanWaitlistEntry": "id makerspace product user quantity status held_quantity offered_at "
                                           "offer_expires_at request created_at updated_at closed_at",
    "machines.MachineJobBatch": "id makerspace machine started_by started_at ended_at note",
    "machines.MachineDowntime": "id makerspace machine kind reason expected_back_at started_at ended_at started_by "
                                "ended_by",
    "maintenance.WorkOrder": "id makerspace subject_type machine product asset space schedule title description "
                             "priority status takes_machine_down due_on assignee resolution log created_by closed_by "
                             "created_at updated_at started_at closed_at",
}
FIELD_ADDITIONS = {
    "inventory.InventoryProduct": "is_consumable public_show_expected_back",
    "procurement.ToBuyItem": "source_consumable vendor",
    "warranty.Warranty": "vendor",
    "hardware_requests.HardwareRequest": "pickup_from pickup_until",
    "machines.MachineServiceRequest": "queued_at urgent urgent_reason needed_by preassigned_machine batch copies own_material material_note member_estimate_minutes changes_requested_at changes_code changes_message member_note reject_code quote_snapshot quote_digest quoted_at quote_expires_at quote_reminded_at quote_approved_at prepay fail_code fail_fault failure_outcome auto_requeue_count pickup_code pickup_location pickup_reminders_sent uncollected_at collected_by_name",
    "machines.MakerspaceMachineTypePolicy": "accepts_job_requests quote_mode quote_above_amount payment_timing member_fault_charge max_open_jobs max_job_minutes runs_unattended file_groups",
    "maintenance.MaintenanceSchedule": "blocks_use",
    "bookings.BookableSpace": "machine",
}
OMITTED_MODELS = {}
# The digest of the frozen quote the member saw; it authenticates nothing.
NON_CREDENTIAL = {
    ("machines.MachineServiceRequest", "quote_digest"): "Integrity digest of the job's frozen price quote, not a secret.",
}
DATASET_SPECS = {
    "procurement.Vendor": ("procurement/vendors.csv", P(("makerspace",))),
    "hardware_requests.LoanReservationPolicy": ("lending/reservation_policy.csv", P(("makerspace",))),
    "hardware_requests.LoanWaitlistEntry": ("lending/waitlist.csv", P(("makerspace",))),
    "machines.MachineJobBatch": ("machine_service/batches.csv", P(("makerspace",))),
    "machines.MachineDowntime": ("machines/downtime.csv", P(("makerspace",))),
    "maintenance.WorkOrder": ("maintenance/work_orders.csv", P(("makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({
    ("procurement.Vendor", "created_by"),
    ("hardware_requests.LoanWaitlistEntry", "user"),
    ("machines.MachineJobBatch", "started_by"),
    ("machines.MachineDowntime", "started_by"),
    ("machines.MachineDowntime", "ended_by"),
    ("maintenance.WorkOrder", "assignee"),
    ("maintenance.WorkOrder", "created_by"),
    ("maintenance.WorkOrder", "closed_by"),
})
# A frozen quote (component names, prices, rule ids) and a list of format group names.
JSON_FIELDS = frozenset({
    ("machines.MachineServiceRequest", "quote_snapshot"),
    ("machines.MakerspaceMachineTypePolicy", "file_groups"),
})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    for label, extra in FIELD_ADDITIONS.items():
        fields[label] += " " + extra
    return fields
