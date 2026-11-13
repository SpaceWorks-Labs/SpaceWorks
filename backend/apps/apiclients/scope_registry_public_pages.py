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
        from apps.makerspaces.profile_images import home_space
        space = home_space(claim.user)  # the profile is global: the person's home space
    return PublicHandleTarget("tenant", space), True


def is_global_target(target):
    return isinstance(target, PublicHandleTarget) and target.kind == "global"
