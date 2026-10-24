"""Core finance authority never depends on event grants or the payments rail."""
from apps.accounts import rbac
from apps.accounts.account_kind_guards import require_member_account
from apps.accounts.reauthentication import binding, require_recent_reauth
from apps.makerspaces.servability import is_servable
from apps.makerspaces.origin_scope import origin_scoped_makerspace_id
from apps.accounts.claim_sessions import claim_context
from apps.makerspaces.models import MakerspaceMembership
from .errors import require
from django.utils import timezone


def authorize(request, space, *, owner_id=None, payout=False, mutation=False, owner=False):
    actor = request.user
    require(getattr(actor, "account_kind", None) in ("member", "staff", "platform"), "full_session_required", status=403)
    require(claim_context(actor) is None, "full_session_required", status=403)
    binding(request)  # Reject API clients, native/device grants and partial sessions.
    token = getattr(request, "auth", None)
    if token is not None and token.get("exp") is not None:
        require(type(token["exp"]) is int and token["exp"] > timezone.now().timestamp(), "session_expired", status=403)
    require(actor.is_active and actor.access_status == "active" and not actor.must_change_password,
            "account_inactive", status=403)
    require(is_servable(space), "not_found", status=404)
    origin_id = origin_scoped_makerspace_id(request)
    require(origin_id is None or origin_id == space.pk, "not_found", status=404)
    if owner:
        require_member_account(actor)
        require(owner_id is not None and actor.pk == owner_id, "not_found", status=404)
        require(not MakerspaceMembership.objects.filter(user=actor, makerspace=space).exclude(status="active").exists(),
                "account_restricted", status=403)
    else:
        require(rbac.can(actor, rbac.Action.VIEW_FINANCE, space.pk), "finance_required", status=403)
        if payout:
            require(rbac.can(actor, rbac.Action.RECORD_REIMBURSEMENT_PAYOUT, space.pk),
                    "payout_recording_forbidden", status=403)
    if mutation and not owner:
        require_recent_reauth(request)
    return actor
