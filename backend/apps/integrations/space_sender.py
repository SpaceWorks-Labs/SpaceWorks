"""A space's own display name and Reply-To on the email it sends (parity E-B8, A19).

Only the display name and the Reply-To change: the From ADDRESS, the provider connection, suppressions, quotas and
the email module gate are untouched, so this cannot make a space send as someone else. A co-hosting organisation's
event sender (`org_sender`) is applied after this and wins for that event's mail. A failure leaves the plain sender.
"""

import logging
from email.utils import formataddr, parseaddr

logger = logging.getLogger(__name__)


def apply(log, msg):
    try:
        from apps.makerspaces.platform import feature_enabled
        space = log.makerspace
        if space is None or not feature_enabled(space, "email.sender_identity"):
            return
        name = (space.email_from_name or "").strip().replace("\r", " ").replace("\n", " ")
        _current, address = parseaddr(msg.from_email)
        if name and address:
            msg.from_email = formataddr((name[:120], address))
        if space.email_reply_to:
            msg.reply_to = [space.email_reply_to]
    except Exception:
        logger.warning("space_sender_apply_failed", extra={"email_log_id": getattr(log, "pk", None)})
