"""Release-2 lane L10 (machine-integration foundations, #76): literal export classification.

`devices.MachineTypeIntegration` is configuration of a DEFERRED integration: a moved or
restored device re-enrolls and is re-bound on its target, so the binding is re-made there.
`devices.PrinterStatusSnapshot` is advisory telemetry kept as one row per device,
overwritten in place: operational data with no history, never tenant data.
"""

OMITTED_MODELS = {
    "devices.MachineTypeIntegration": (
        "Deferred machine-integration binding (#76); devices re-enroll on a target and are re-bound there."
    ),
    "devices.PrinterStatusSnapshot": "Latest advisory printer telemetry, overwritten in place; never tenant history.",
}
EXCLUDED_USER_EDGE_REASONS = {
    ("devices.MachineTypeIntegration", "created_by"): "Staff attribution of an omitted deferred binding.",
}
RELATIONAL_USER_FIELDS = frozenset(EXCLUDED_USER_EDGE_REASONS)
