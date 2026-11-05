"""Platform IP rule edits shared by /control/ and the web console (#190): one lock-out guard, one unblock.

A deny rule that covers the editor's own address, with no allow rule covering it, would
lock the superadmin out of every sign-in page the moment it is saved.
"""

from apps.accounts import ip_rules
from apps.accounts.login_security_contract import IP_ALLOW, IP_DENY
from apps.audit import services as audit

LOCKOUT_MESSAGE = ("This deny rule covers the address you are using now and would lock you out. "
                   "Add an allow rule for your own address first.")


def would_lock_out(editor_address, cidr, action, *, replacing_cidr=None):
    """True when saving (cidr, action) leaves ``editor_address`` denied and not allowed."""
    if action != IP_DENY or not cidr or editor_address is None:
        return False
    if not ip_rules.covering(editor_address, IP_DENY, [(cidr, IP_DENY, None)]):
        return False
    others = [rule for rule in ip_rules.active_rules() if rule[0] != replacing_cidr]
    return not ip_rules.covering(editor_address, IP_ALLOW, others)


def unblock(actor, rows):
    """Lift automatic blocks now; one ``auth.ip_unblocked`` row each. Returns the count."""
    count = 0
    for row in list(rows):
        audit.record(actor, "auth.ip_unblocked", target=row, meta={"ip_key": row.ip_key})
        row.delete()
        count += 1
    return count
