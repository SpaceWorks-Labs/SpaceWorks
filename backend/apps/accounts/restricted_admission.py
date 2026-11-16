"""Decision 260: what a restricted or suspended account may still reach.

Paying a debt is how a restriction is cleared, so locking a restricted or suspended person
out of their own charges made the restriction permanent. `member_may_see_own_charges` has
admitted such an account since G-1, but the session boundary (`surface_policy._active`,
`authentication_device.validated_device_grant`) refused every non-active account first, so
the admission was never reached on the web or the phone.

The exception is deliberately narrow:

* only the own-charge routes (`OWN_CHARGE_ROUTES`, the same set a membership-less borrower
  may select on the phone), the signed receipt download, the outstanding-per-currency
  summary (`my-usage`, which answers a restricted account with its payments alone), and
  sign-out;
* only for a person's browser session or a native MEMBER grant -- a staff or event grant of a
  restricted account stays refused, so no staff authority is ever exercised;
* every admitted view re-checks ownership itself (`member_may_see_own_charges`,
  `member_payment_queryset`, the signed document grant), and a REVOKED member stays refused.

Everything else keeps the typed 401 `account_restricted` / `account_suspended`
(`account_status_refusal.py`).

Decision 361: such a PERSON may also sign in and refresh (every factor and MFA rule unchanged),
because the resulting session is held to this same admission on every request. Issuance asks
`state_may_sign_in`; the request gate (`surface_policy.enforce_request`, `validated_device_grant`)
asks `restricted_route_admitted`. A platform account, and any staff or event grant, still needs
an ACTIVE account; deactivated, retired and merged accounts never sign in.
"""

RESTRICTED_STATES = frozenset({"restricted", "suspended"})
ACTIVE = "active"
SIGN_OUT_ROUTES = frozenset({"auth-logout", "auth-logout-all", "device-logout"})
RECEIPT_DOWNLOAD_ROUTES = frozenset({"payment-document-download"})
OUTSTANDING_SUMMARY_ROUTES = frozenset({"member-my-usage"})


def restricted_admitted_routes():
    """Every url name a restricted or suspended session may still reach."""
    from apps.makerspaces.origin_scope_own_charges import OWN_CHARGE_ROUTES

    return OWN_CHARGE_ROUTES | RECEIPT_DOWNLOAD_ROUTES | OUTSTANDING_SUMMARY_ROUTES | SIGN_OUT_ROUTES


def restricted_route_admitted(user, request):
    """Whether this restricted/suspended account may make THIS request despite its state.

    False for an active account (nothing to admit) and for any other inactive state
    (deactivated, retired, merged), which stay refused everywhere.
    """
    if request is None or getattr(user, "access_status", None) not in RESTRICTED_STATES:
        return False
    from apps.accounts.staff_identity import is_person

    if not getattr(user, "is_active", False) or not is_person(user):
        return False
    name = getattr(getattr(request, "resolver_match", None), "url_name", None)
    return name in restricted_admitted_routes()


def state_may_sign_in(user):
    """Whether this ``access_status`` may hold a session at all (decision 361).

    Active always; restricted or suspended only for a person. The other liveness checks
    (``is_active``, retired, merged, stub, deletion) stay with each caller.
    """
    status = getattr(user, "access_status", None)
    if status == ACTIVE:
        return True
    from apps.accounts.staff_identity import is_person

    return status in RESTRICTED_STATES and is_person(user)


def account_status(user):
    """The typed state the sign-in payload reports: ``active``, ``restricted`` or ``suspended``."""
    status = getattr(user, "access_status", ACTIVE)
    return status if status in RESTRICTED_STATES else ACTIVE
