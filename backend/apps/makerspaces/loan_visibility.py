"""Frontend loan surfaces suppressed by the per-space master switch."""

LOAN_MODULES = frozenset({
    "public_inventory", "request_workflow", "guest_handover", "evidence_uploads",
    "qr_management", "scanner", "bulk_import", "containers", "stock_transfers",
    "stocktake", "qr_print_batches", "asset_units",
})
# Modules that only Inventory uses. `module_enabled` answers False for them while the Inventory
# switch (`loans.enabled`) is off, so every `require_module` route guard refuses with the standard
# typed 404 without each view naming the switch. `scanner`, `evidence_uploads` and `qr_management`
# are left out on purpose: machine handover and member-card QR share them.
INVENTORY_ONLY_MODULES = frozenset({
    "public_inventory", "request_workflow", "guest_handover", "bulk_import", "containers",
    "stock_transfers", "stocktake", "qr_print_batches", "asset_units",
})
# Every child of the Inventory switch. `inventory.consumables`/`inventory.vendors` (machine-scoped supplies) and
# `loans.fee_waivers` (money on retained loans) deliberately keep their own state.
LOAN_FEATURES = frozenset({
    "inventory.self_checkout", "inventory.kiosk", "inventory.contact_self_checkout", "inventory.expected_back",
    "inventory.issue_reporting", "inventory.maintenance", "inventory.maintenance_reminders",
    "inventory.notify_when_back", "inventory.repairs", "inventory.tobuy", "inventory.warranty",
    "loans.renewals", "loans.limits", "loans.kit_checklist", "loans.reservations", "loans.pickup_windows",
    "loans.waitlist", "loans.withdrawals",
})
# Loan policies and money remain available for retained loans. A visibility switch
# must not prevent a returned loan from recording a late fee or settling its debt.
