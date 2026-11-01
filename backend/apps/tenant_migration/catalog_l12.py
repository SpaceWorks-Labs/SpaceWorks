"""Release-2 lane L12 (machines and loans depth): tenant-dump field snapshot and authority.

Every L12 row is the space's own operational record (data_export `classification_l12`)
and travels with it; foreign keys remap like any other. Nothing here is a credential or
a bearer capability.
"""

JOB_FIELDS = ("queued_at urgent urgent_reason needed_by preassigned_machine batch copies own_material material_note member_estimate_minutes changes_requested_at changes_code changes_message member_note reject_code quote_snapshot quote_digest quoted_at quote_expires_at quote_reminded_at quote_approved_at prepay fail_code fail_fault failure_outcome auto_requeue_count pickup_code pickup_location pickup_reminders_sent uncollected_at collected_by_name")
POLICY_FIELDS = "accepts_job_requests quote_mode quote_above_amount payment_timing member_fault_charge max_open_jobs max_job_minutes runs_unattended file_groups"
JOB_SCALARS = " ".join(name for name in JOB_FIELDS.split() if name not in ("preassigned_machine", "batch"))
FIELD_NAMES = {
    "procurement.Vendor": frozenset(
        "id makerspace name contact_name email phone website notes is_archived created_by created_at "
        "updated_at".split()),
    "hardware_requests.LoanReservationPolicy": frozenset(
        "id makerspace pickup_window_hours reservation_max_days_ahead waitlist_offer_hours updated_at".split()),
    "hardware_requests.LoanWaitlistEntry": frozenset(
        "id makerspace product user quantity status held_quantity offered_at offer_expires_at request created_at "
        "updated_at closed_at".split()),
    "machines.MachineJobBatch": frozenset("id makerspace machine started_by started_at ended_at note".split()),
    "machines.MachineDowntime": frozenset(
        "id makerspace machine kind reason expected_back_at started_at ended_at started_by ended_by".split()),
    "maintenance.WorkOrder": frozenset(
        "id makerspace subject_type machine product asset space schedule title description priority status "
        "takes_machine_down due_on assignee resolution log created_by closed_by created_at updated_at started_at "
        "closed_at".split()),
}
EXTRA_FIELDS = {
    "inventory.InventoryProduct": frozenset({"is_consumable", "public_show_expected_back"}),
    "procurement.ToBuyItem": frozenset({"source_consumable", "vendor"}),
    "warranty.Warranty": frozenset({"vendor"}),
    "hardware_requests.HardwareRequest": frozenset({"pickup_from", "pickup_until"}),
    "machines.MachineServiceRequest": frozenset(JOB_FIELDS.split()),
    "machines.MakerspaceMachineTypePolicy": frozenset(POLICY_FIELDS.split()),
    "maintenance.MaintenanceSchedule": frozenset({"blocks_use"}),
    "bookings.BookableSpace": frozenset({"machine"}),
}
PROJECTED_LABELS = frozenset(FIELD_NAMES)


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    keep = disposition.PRESERVE
    return (
        *same("inventory.InventoryProduct", "is_consumable public_show_expected_back", keep,
              "Item configuration is the space's own catalogue data."),
        *same("hardware_requests.HardwareRequest", "pickup_from pickup_until", keep,
              "A request's pickup window is part of its own workflow history."),
        *same("procurement.Vendor", "name contact_name email phone website notes is_archived created_at updated_at",
              keep, "A saved supplier is the space's own business record."),
        *same("hardware_requests.LoanReservationPolicy", "pickup_window_hours reservation_max_days_ahead "
              "waitlist_offer_hours updated_at", keep, "Pickup and waitlist timing are the space's own policy."),
        *same("hardware_requests.LoanWaitlistEntry", "quantity status held_quantity offered_at offer_expires_at "
              "created_at updated_at closed_at", keep,
              "A waitlist place and its held units travel with the stock they hold."),
        *same("machines.MachineServiceRequest", JOB_SCALARS, keep,
              "A job's queue place, quote, outcome and pickup details are its own workflow history."),
        *same("machines.MakerspaceMachineTypePolicy", POLICY_FIELDS, keep,
              "Per-type job settings are the space's own configuration."),
        *same("maintenance.MaintenanceSchedule", "blocks_use", keep, "A schedule's lockout flag is its own policy."),
        *same("machines.MachineJobBatch", "started_at ended_at note", keep, "A batch run is machine history."),
        *same("machines.MachineDowntime", "kind reason expected_back_at started_at ended_at", keep,
              "The downtime ledger is the machine's own history."),
        *same("maintenance.WorkOrder", "subject_type title description priority status takes_machine_down due_on "
              "resolution created_at updated_at started_at closed_at", keep,
              "A work order is the space's own maintenance record."),
    )
