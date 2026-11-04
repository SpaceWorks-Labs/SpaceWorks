"""Who an account is, and what staff authority it holds (one account per person).

The single seam for identity predicates; callers never read ``User.account_kind`` or
``User.staff_makerspace`` themselves:

- a **person** is ``account_kind="member"`` (shown as ``person`` in the API) and is the
  only kind that holds memberships, grants or sessions of its own;
- a **platform** account is the superadmin, separate from every person;
- an **inert shell** (``account_kind="staff"``) is a retired or merged account kept only
  so immutable history keeps its actor ids. It never signs in and holds no live row.

Staff authority is a staff-TRACK membership on a person (``has_staff_role``). Elevated
authority (``has_elevated_authority``) adds organization authority and resource grants;
mandatory MFA keys on it, with the superadmin exempt (login-security §2).
"""

from django.db.models import Exists, OuterRef, Q

PERSON_KIND = "member"
PLATFORM_KIND = "platform"
SHELL_KIND = "staff"
_ALIAS_DEPTH = 32


def person_q(prefix=""):
    """Q for person accounts, optionally through a relation (``"user__"``).

    The account-context constraint keeps retired and merged accounts off this kind, so
    the kind alone is exact.
    """
    return Q(**{f"{prefix}account_kind": PERSON_KIND})


def platform_q(prefix=""):
    return Q(**{f"{prefix}account_kind": PLATFORM_KIND})


def shell_q(prefix=""):
    return Q(**{f"{prefix}account_kind": SHELL_KIND})


def is_person(user):
    return (getattr(user, "account_kind", None) == PERSON_KIND
            and getattr(user, "retired_at", None) is None
            and getattr(user, "merged_into_id", None) is None)


def is_platform(user):
    return getattr(user, "account_kind", None) == PLATFORM_KIND


def is_shell(user):
    return getattr(user, "account_kind", None) == SHELL_KIND


def context_label(user):
    """The stored kind as an opaque label, for binding a session to the account it was
    minted for. Never an authority test: use the predicates above for that."""
    return getattr(user, "account_kind", None)


def _live_person(user):
    return bool(user is not None and getattr(user, "is_authenticated", False)
                and getattr(user, "pk", None) is not None and getattr(user, "is_active", False)
                and not getattr(user, "is_tenant_dump_stub", False) and is_person(user))


def _staff_rows(makerspace_id=None):
    from apps.accounts.membership_context import valid_staff_membership_q
    from apps.makerspaces.models import MakerspaceMembership

    rows = MakerspaceMembership.staff_tracks.filter(valid_staff_membership_q(), status="active")
    return rows if makerspace_id is None else rows.filter(makerspace_id=makerspace_id)


def staff_makerspace_ids(user):
    """Servable makerspaces where the person holds an active, valid staff-track row."""
    if not _live_person(user):
        return set()
    from apps.makerspaces.servability import unservable_makerspace_ids

    ids = set(_staff_rows().filter(user_id=user.pk).values_list("makerspace_id", flat=True))
    return ids - set(unservable_makerspace_ids()) if ids else ids


def has_staff_role(user, makerspace_id=None):
    """The staff track only; platform accounts and shells always return False."""
    ids = staff_makerspace_ids(user)
    if makerspace_id is None:
        return bool(ids)
    try:
        return int(makerspace_id) in ids
    except (TypeError, ValueError):
        return False


def staff_holder_q(makerspace_id=None, prefix=""):
    """Q over a User queryset (or through ``prefix``) for people holding an active, valid
    staff-track row, in one makerspace or anywhere. Servability is the caller's scope."""
    rows = _staff_rows(makerspace_id).filter(user_id=OuterRef(f"{prefix}pk"))
    return person_q(prefix) & Q(Exists(rows))


def has_elevated_authority(user):
    """Staff role, organization authority or a resource grant anywhere servable."""
    if not _live_person(user):
        return False
    if has_staff_role(user):
        return True
    from apps.accounts import rbac
    from apps.makerspaces.resource_grant_sources import has_authority

    return has_authority(user) or rbac.has_any_org_authority(user)


def actor_ids_for(user):
    """``{user.id}`` plus every shell merged into it, transitively."""
    if user is None or getattr(user, "pk", None) is None:
        return set()
    from apps.accounts.models import User

    ids, frontier = {user.pk}, {user.pk}
    for _ in range(_ALIAS_DEPTH):
        frontier = set(User._base_manager.filter(merged_into_id__in=frontier)
                       .exclude(pk__in=ids).values_list("pk", flat=True))
        if not frontier:
            return ids
        ids |= frontier
    raise RuntimeError("Merged-account alias chain is deeper than expected.")


def require_staff_mfa(user, claims, *, route=None):
    """The staff gate: every staff route and staff device grant (login-security S-A).

    Passes only on VERIFIED proof by ``totp``, ``recovery`` or ``passkey`` bound to the
    live ``UserMFA.version`` (provider, emailed-code, none and bypass proof never pass),
    or while an unenrolled person's 3-day grace is open (#128 C-1) on a route outside
    ``mfa_grace.STRICT_ROUTES`` (#135 Q-A3). A browser session past its staff session
    length or idle timeout is refused too. Refusals are 403s, so the member session
    itself keeps working.
    """
    from rest_framework.exceptions import PermissionDenied

    from apps.accounts import mfa_grace, mfa_policy
    from apps.accounts.login_security_contract import MFA_ENROLLMENT_REQUIRED, MFA_REQUIRED
    from apps.accounts.staff_session_policy import assert_staff_session

    assert_staff_session(user, claims)
    if not mfa_policy.required(user) or mfa_policy.verified_staff_proof(user, claims):
        return
    if mfa_policy.staff_factor_enrolled(user):
        raise PermissionDenied({"detail": "Verify with your second factor to use staff screens.",
                                "code": MFA_REQUIRED})
    if route not in mfa_grace.STRICT_ROUTES and mfa_grace.is_open(user):
        return
    raise PermissionDenied({"detail": "Set up two-step sign-in to use staff screens.",
                            "code": MFA_ENROLLMENT_REQUIRED})
