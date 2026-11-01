"""Platform mail for account merges: the two proof codes and the "accounts linked" notice.

Platform connection, never persisted (``persist_body=False``) and, like sign-in alerts,
outside every per-space opt-out: a person cannot unsubscribe from proving who they are.
A failed send is logged by type only; callers never reveal it (no enumeration).
"""

import logging

logger = logging.getLogger(__name__)
_SIDES = {
    "survivor": "to link another account to the one you are signed in to",
    "source": "to link this account to the account you are signed in to",
}


def _send(address, subject, body, event):
    from apps.integrations.dispatch import dispatch_email

    try:
        log = dispatch_email(to_email=address, subject=subject, text_body=body, stream="account",
                             event=event, audience="user", connection="platform",
                             persist_body=False, sync=True)
        return log.status in {"sent", "delivered"}
    except Exception as exc:
        logger.warning("account_merge_mail_failed", extra={"event": event, "error_type": type(exc).__name__})
        return False


def send_code(address, code, *, side):
    return _send(address, "Your Space Works account link code",
                 f"Your code {_SIDES[side]} is {code}. It expires in 10 minutes and works once.\n\n"
                 "Space Works never asks for this code by phone or chat. If you did not start "
                 "linking accounts, ignore this email; nothing changes without both codes.",
                 "account_merge_code")


def send_linked(addresses):
    body = ("Two Space Works accounts were linked into one. Sign in with the account you were "
            "signed in to when you linked them; the other account no longer signs in, and its "
            "history and roles now belong to the remaining account.\n\n"
            "If you did not do this, contact your makerspace or the platform operator at once.")
    for address in sorted({address.strip().lower() for address in addresses if address and address.strip()}):
        _send(address, "Your Space Works accounts were linked", body, "account_merged")
