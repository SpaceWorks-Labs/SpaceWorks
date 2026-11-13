"""The observation record and the tenant-target verdict (split from `scope_registry.py`).

Re-exported from ``scope_registry``; ``classify`` in the barrel calls ``target_allows``.
"""
from dataclasses import dataclass

from apps.apiclients.scope_registry_routes import TARGET_GLOBAL

from .scope_registry_public_pages import is_global_target


@dataclass(frozen=True, slots=True)
class ScopeObservation:
    view_name: str | None
    method: str
    verdict: bool
    target_resolution: str
    target_resolved: bool | None
    target_makerspace_id: int | None


PEER_CLIENT_TYPE = "peer"


def peer_may_reach(entry, method=None):
    """A peer (space-to-space) client reads its own space's public catalogue, events and stats.

    Enforced here as well as at grant time, so a peer row that somehow holds a wider
    scope (an edited row, a restored dump) still reaches nothing else.
    """
    from .scope_registry_areas import PEER_AREAS
    return (entry.access == "read" and entry.area in PEER_AREAS
            and (method is None or method.upper() in ("GET", "HEAD")))


def target_allows(entry, client, target, resolved):
    client_type = getattr(client, "client_type", None)
    if entry.server_only and client_type != "server":
        return False
    if client_type == PEER_CLIENT_TYPE and (client.makerspace_id is None or not peer_may_reach(entry)):
        return False
    if entry.tenant_bound and client.makerspace_id is None:
        return False
    if not resolved:
        return False
    if entry.target_mode == TARGET_GLOBAL or is_global_target(target):
        return client.makerspace_id is None or entry.tenant_apps_admitted
    target_id = getattr(target, "pk", None)
    if target_id is None:
        return False
    return client.makerspace_id is None or target_id == client.makerspace_id
