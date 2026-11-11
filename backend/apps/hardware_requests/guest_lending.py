"""Decision 223 (c): a guest-pass holder in the lending paths.

One module answers every "is this borrower a pass holder, and what may they do" question for
request submit, contextual equipment intake, self-checkout, the desk handout and the reviewed
issue, so the paths cannot drift:

* `admit_borrower` -- members go through the existing guards (and the lapsed-term rule); a
  non-member is admitted only by a live pass whose borrowing mode is not `none`.
* `cap_due` -- an `on_site` pass makes the loan due no later than the pass end. A computed due
  is clamped; a staff-entered one past the pass end is refused (`guest_pass_on_site_only`).
* `guest_issue_gate` -- the reviewed-issue check for a non-member requester: a live pass with
  borrowing, the current waiver, and for `full_with_deposit` the mandatory deposit (the item's
  own deposit; an item with none cannot be taken away by a guest -- `guest_pass_deposit_required`).

Per-person accountability is unchanged: the pass holder is the requester of record.
"""
from apps.accounts.staff_identity import is_person
from apps.makerspaces.guest_pass_policy import GuestPassError, guest_passes_on
from apps.makerspaces.guest_pass_queries import active_pass_for, pass_entitlements
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.opening_hours import previous_close
from apps.makerspaces.request_access import require_current_term
from apps.presence.guest_guard import require_borrowing, require_guest_waiver, require_member_or_guest


def admit_borrower(makerspace, borrower, *, presence=True, planning=False):
    """Admit a member or a pass holder; returns `ActiveMemberPresence` (`.guest_pass` set for a guest)."""
    active = require_member_or_guest(borrower, makerspace, presence=presence, borrow=True, planning=planning)
    if active.guest_pass is None:
        require_current_term(makerspace, active.membership)
    return active


def admit_self_checkout(makerspace, user, *, taking):
    """Self-checkout: a member as before; a pass holder only on an `on_site` pass (the desk takes deposits).

    Returning a tool needs a live pass too but is never gated by the borrowing mode.
    """
    active = require_member_or_guest(user, makerspace, borrow=taking)
    if active.guest_pass is None:
        if taking:
            require_current_term(makerspace, active.membership)
    elif taking and pass_entitlements(active.guest_pass).borrow == "full_with_deposit":
        raise GuestPassError("guest_pass_deposit_required",
                             "Taking items away needs a deposit; ask the desk to hand them over.", status_code=403)
    return active


def _is_member(makerspace, user):
    return MakerspaceMembership.objects.filter(makerspace=makerspace, user=user, status="active").exists()


def borrowing_pass(makerspace, requester, at=None):
    """The live pass when `requester` is a non-member pass holder here, else None."""
    if requester is None or not guest_passes_on(makerspace) or _is_member(makerspace, requester):
        return None
    return active_pass_for(requester, makerspace, at)


def cap_due(makerspace, requester, due, *, at=None, staff_entered=False):
    """`due`, or the pass end when an on-site pass would otherwise outlive itself."""
    guest_pass = borrowing_pass(makerspace, requester, at)
    if guest_pass is None or due is None:
        return due
    ent = pass_entitlements(guest_pass)
    if not ent.on_site_only or due <= ent.due_by:
        return due
    if staff_entered:
        raise GuestPassError("guest_pass_on_site_only",
                             "This guest pass only covers using items on site; the due time cannot be after the pass ends.",
                             status_code=403)
    return _last_open_close(makerspace, guest_pass)


def _last_open_close(makerspace, guest_pass):
    """The pass end, or when it falls in closed hours the close of the last open session inside the window (#227 m14)."""
    end = guest_pass.valid_until
    close = previous_close(makerspace, end)
    return close if close is not None and close > guest_pass.valid_from else end


def _deposit_priced(request):
    """The deposit this loan would owe, or a `guest_pass_deposit_required` refusal when there is none."""
    from apps.hardware_requests.loan_charges_common import fee_exempt, loans_enabled
    from apps.hardware_requests.loan_charges_issue import deposit_quote

    if fee_exempt(request) or not loans_enabled(request.makerspace):
        priced = None  # no account to bill, or deposits are not recorded in this space
    else:
        priced = deposit_quote(request)
    if priced is None or priced.total <= 0:
        raise GuestPassError("guest_pass_deposit_required",
                             "A guest must leave a deposit to take items away, and this one has no deposit set.",
                             status_code=403)
    return priced


def require_deposit_possible(request, guest_pass):
    """Desk handout (the request is born issued): refuse a `full_with_deposit` loan that can owe no deposit.

    The deposit itself is raised after commit by the normal `on_request_issued` hook.
    """
    if pass_entitlements(guest_pass).borrow == "full_with_deposit":
        _deposit_priced(request)


def require_guest_deposit(request, actor, guest_pass):
    """`full_with_deposit`: the item's deposit must exist and be settled before the guest takes it away."""
    from apps.hardware_requests.loan_charges_issue import _deposit
    from apps.hardware_requests.models import HardwareRequest
    from apps.hardware_requests.workflow_errors import DepositRequired
    from apps.payments.models import Payment

    if request.status != HardwareRequest.Status.ACCEPTED:
        return None
    payment = _deposit(request, actor, _deposit_priced(request))
    if payment.status == Payment.Status.PENDING:
        raise DepositRequired(payment)
    return payment


def guest_issue_gate(request, actor):
    """Reviewed issue to a non-member: live pass, borrowing, waiver, and the mandatory deposit."""
    makerspace, requester = request.makerspace, request.requester
    if (requester is None or not is_person(requester) or not guest_passes_on(makerspace)
            or _is_member(makerspace, requester)):
        return None  # anonymous/contact requesters and members are not this gate's business
    guest_pass = active_pass_for(requester, makerspace)
    if guest_pass is None:
        raise GuestPassError("guest_pass_required", "This person is not a member and holds no active guest pass.",
                             status_code=403)
    ent = require_borrowing(guest_pass)
    require_guest_waiver(requester, makerspace, guest_pass)
    if ent.borrow == "full_with_deposit":
        require_guest_deposit(request, actor, guest_pass)
    return guest_pass
