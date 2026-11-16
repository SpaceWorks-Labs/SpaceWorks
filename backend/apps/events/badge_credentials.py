"""The check-in code a printed badge carries (parity E-B2).

Reading never rotates: a v2 credential that has expired or was revoked yields `None`, and the badge prints a
"Print at the desk" placeholder instead of minting a new code. Rotation stays the explicit staff action in
`credentials/workflow.py`, because a new code kills the one already in the holder's wallet.
"""


def current_checkin_payload(registration):
    """The registration's live check-in code, or None when it has none to print."""
    if registration.credential_mode == "legacy":
        return str(registration.checkin_token)
    if registration.credential_mode != "v2":
        return None
    from .credentials.crypto import unwrap
    from .credentials.errors import CredentialKeyUnavailable
    from .credentials.workflow import current
    row = current(registration)
    if row is None:
        return None
    try:
        return unwrap(row, registration.event_id)
    except (CredentialKeyUnavailable, ValueError):
        return None
