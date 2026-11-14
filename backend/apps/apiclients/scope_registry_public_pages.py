"""Tagged live handle resolution: a global success is never an unresolved tenant."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PublicHandleTarget:
    kind: str
    makerspace: object | None = None

    @property
    def pk(self):
        return getattr(self.makerspace, "pk", None)


def resolve_handle_target(request, match):
    from apps.makerspaces.public_page_access import resolve_handle
    claim, result = resolve_handle(match.kwargs.get("handle"), request)
    if result["kind"] == "organization":
        return PublicHandleTarget("global"), True
    if result["kind"] == "makerspace":
        space = claim.makerspace
    else:
        return resolve_card_target(request, claim.handle)
    return PublicHandleTarget("tenant", space), True


def resolve_card_target(request, handle):
    """549: live card admission, independent of legacy consent or a profile row.

    A verified tenant targets its qualifying public membership. Unscoped reads
    retain home/global resolution; client scopes and tenant-app rules still apply.
    """
    from rest_framework.exceptions import NotFound
    from apps.makerspaces.account_profile_spaces import listed_memberships, _public_space
    from apps.makerspaces.public_profile_access import _request_tenant_ids
    from apps.makerspaces.public_profile_card import resolve_card_handle
    from apps.makerspaces.profile_images import home_space
    claim, _ = resolve_card_handle(handle, request)
    scopes = set(_request_tenant_ids(request))
    if len(scopes) > 1:
        raise NotFound()
    if scopes:
        membership = listed_memberships(claim.user).filter(makerspace_id=next(iter(scopes))).first()
        if membership and _public_space(membership.makerspace):
            return PublicHandleTarget("tenant", membership.makerspace), True
    space = home_space(claim.user)
    return PublicHandleTarget("tenant", space) if space else PublicHandleTarget("global"), True


def is_global_target(target):
    return isinstance(target, PublicHandleTarget) and target.kind == "global"
