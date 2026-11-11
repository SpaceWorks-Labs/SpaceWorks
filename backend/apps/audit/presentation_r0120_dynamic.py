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
))
WRAPPERS = {
    "card_designs/wallet/credential_service.py": ("wallet_pass.credentials_",),
}
