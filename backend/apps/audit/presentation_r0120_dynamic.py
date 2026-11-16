"""Reviewed 0.12.0 dynamic audit sites; their metadata is denied by default.

The L3a supervised-session, induction-unlink and incident services build their `meta` with a
shared helper (`_meta(...)`), so the drift guard sees a non-literal dict: those actions keep a
catalogue label and project `meta={}` in staff views while the raw audit row keeps every id.
The wallet credential service passes its action through `_record`, so it takes the wrapper
deny policy by prefix.
"""

NON_LITERAL = frozenset((
    "certification.induction_unlinked",
    "incident.reported", "incident.status_changed", "incident.updated",
    "machine_session.supervised_opened", "machine_session.supervised_closed",
    "machine_session.supervised_use_started", "machine_session.supervised_use_ended",
    "machine_session.supervisee_added", "machine_session.supervisee_removed",
    # Final 0.12.0 round: emitters that build `meta` at runtime (metadata denied in staff views).
    "devices.adapter_auto_off", "event.submission_reinstated", "machine_access.granted", "machine_access.renewed",
    "machine_event.cost_approved", "machine_event.cost_withdrawn", "machine_event.linked", "payment.paid_online",
))
# Dynamic actions that only ever yield string constants (two-way conditional or constant-assigned variable).
EXACT = frozenset((
    "devices.adapter_talk_started", "devices.adapter_talk_stopped", "staff_card.auto_issued", "staff_card.issued",
    "card.photo_eraser_opted_in", "card.photo_eraser_opted_out",
))
WRAPPERS = {
    "card_designs/wallet/credential_service.py": ("wallet_pass.credentials_",),
    # Final 0.12.0 round: services that pass the action through a helper or an f-string.
    "card_designs/cutouts.py": ("card.photo_cutout_",),
    "card_designs/image_adapter/provider.py": ("image_adapter.",),
    "card_designs/templates.py": ("card_template.",),
    "card_designs/wallet/devices.py": ("wallet_pass.device_",),
    "devices/services_adapter_core.py": ("devices.adapter_",),
    "devices/services_shelf_pointer.py": ("devices.adapter_",),
    "events/machine_use_services.py": ("machine_event.",),
    "machines/consumable_profile_services.py": ("machine_type_consumable.",),
    "organizations/services_review.py": ("organization.review_",),
}
