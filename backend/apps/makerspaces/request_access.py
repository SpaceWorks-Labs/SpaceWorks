"""Who may submit a borrow request — the single answer, in one place (owner decisions #80/#91).

Derived, never stored; there is no opt-in switch (`makerspaces/0105` dropped the old one).

===================  ===========  ==============================================
`member_accounts`    `membership` who may submit
===================  ===========  ==============================================
on                   on           ``members``  — an active MakerspaceMembership
on                   off          ``accounts`` — any active signed-in account
off                  (off)        ``contact``  — no account: name + phone + email,
                                  the email confirmed with a one-time code
===================  ===========  ==============================================

`membership` requires `member_accounts` (#91), so the last row never has it. A space
without member accounts has accounts for STAFF only, so EVERYONE there -- signed in or
not -- requests and self-checks-out by the contact path (#91). Its requests are recorded
against the makerspace's inert `anonymous_requester` principal with an encrypted snapshot.
"""

MEMBERSHIP_MODULE = "membership"
MEMBER_ACCOUNTS_MODULE = "member_accounts"

MEMBERS = "members"
ACCOUNTS = "accounts"
CONTACT = "contact"

POLICY_LABELS = {
    MEMBERS: "active members of this makerspace",
    ACCOUNTS: "anyone with a signed-in account",
    CONTACT: "anyone, with name, phone and a confirmed email (no account)",
}


def membership_installed(enabled_modules) -> bool:
    """Pure predicate over the stored key list.

    Deliberately NOT ``platform.module_enabled``: that also asks whether the deployment
    still ships the app, and this is the fail-closed direction. A tenant that asked for
    membership must not be widened to every account just because the app is tombstoned.
    """
    return MEMBERSHIP_MODULE in set(enabled_modules or [])


def effective_policy(makerspace) -> str:
    """Who may submit to this makerspace right now."""
    from apps.makerspaces.platform import module_enabled

    if not module_enabled(makerspace, MEMBER_ACCOUNTS_MODULE):
        return CONTACT
    return MEMBERS if membership_installed(makerspace.enabled_modules) else ACCOUNTS


def contact_requests_allowed(makerspace) -> bool:
    return effective_policy(makerspace) == CONTACT


def uses_contact_path(request, makerspace) -> bool:
    """Whether this caller borrows by the contact path (#80/#91).

    Without member accounts EVERY account -- staff and organisation sign-ins included --
    uses the contact form. A walk-in's claim session is the exception: it is not an
    account but the staff-created person record itself (Phase 7), so it keeps acting as
    that person and every handover stays attributed to them.
    """
    return contact_requests_allowed(makerspace) and getattr(request, "claim_session", None) is None


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
