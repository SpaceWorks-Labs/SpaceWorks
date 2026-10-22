"""Who may submit a borrow request — the single answer, in one place.

Every borrow request needs a signed-in account (owner decision #75f removed the
account-less opt-in). Which accounts is DERIVED, never stored: it falls out of whether
the ``membership`` module is installed.

===========  ============================================
`membership` who may submit
===========  ============================================
on           ``members``  — an active MakerspaceMembership
off          ``accounts`` — any active authenticated account
===========  ============================================
"""

MEMBERSHIP_MODULE = "membership"

MEMBERS = "members"
ACCOUNTS = "accounts"

POLICY_LABELS = {
    MEMBERS: "active members of this makerspace",
    ACCOUNTS: "anyone with a signed-in account",
}


def membership_installed(enabled_modules) -> bool:
    """Pure predicate over the stored key list.

    Deliberately NOT ``platform.module_enabled``: that also asks whether the deployment
    still ships the app, and this is the fail-closed direction. A tenant that asked for
    membership must not be widened to every account just because the app is tombstoned,
    and the model layer cannot import ``platform`` anyway (``platform`` imports the models).
    """
    return MEMBERSHIP_MODULE in set(enabled_modules or [])


def policy_for(enabled_modules) -> str:
    return MEMBERS if membership_installed(enabled_modules) else ACCOUNTS


def effective_policy(makerspace) -> str:
    """Who may submit to this makerspace right now."""
    return policy_for(makerspace.enabled_modules)


def require_current_term(makerspace, membership):
    """The optional "lapsed members cannot borrow" rule, applied AFTER membership passed.

    Plans are optional, so this is deliberately narrow: a member who has never held a
    term is untouched, and the flag off means nothing here runs. Only a member whose
    every term has expired or been cancelled is refused -- and refused with the same
    exception a non-member gets, because that is what the operator asked for. No new
    access state: `MakerspaceMembership.status` and `User.access_status` stay as they are.

    Every way a member TAKES a tool calls this: request submission, self-checkout (and
    its issue-evidence presign) and staff direct handout. Returning never does -- a lapsed
    member must always be able to give a tool back. Bookings, events and machine service
    are not borrowing and are not covered. Plans belong to the `membership` module, so the
    rule is inert while that module is off, whatever the stored flag says.
    """
    if (
        membership is None
        or not makerspace.lapsed_members_cannot_borrow
        or not membership_installed(makerspace.enabled_modules)
    ):
        return
    from django.utils import timezone

    from apps.makerspaces.models import MembershipTerm
    from apps.makerspaces.platform import module_enabled

    if not module_enabled(makerspace, MEMBERSHIP_MODULE):
        return

    terms = MembershipTerm.objects.filter(membership=membership)
    from apps.makerspaces.membership_renewals import current_terms
    if not terms.exists() or current_terms(membership):
        return
    from apps.presence.guard import MemberPresenceRequired

    raise MemberPresenceRequired()
