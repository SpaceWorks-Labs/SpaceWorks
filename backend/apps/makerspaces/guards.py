from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound

from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_aliases import canonical_module_key, canonical_module_keys
from apps.makerspaces.module_registry import module_available
from apps.makerspaces.platform import feature_enabled, inventory_master_allows, module_enabled


class SurfaceOff(NotFound):
    """A module or capability that is off for this space (#95, #183B).

    An off switch leaves no API surface, so the route answers 404 like any other
    surface that does not exist here. The body stays typed so a client can tell
    "turned off" from "no such row": ``{"detail", "code", "module"|"feature"}`` where
    ``code`` is ``module_disabled`` or ``feature_disabled`` and the third key names
    the switch. ``message`` is the plain sentence, for Django admin forms and logs.
    """

    def __init__(self, kind, key, message=None):
        self.kind = kind
        self.key = key
        self.message = message or f"{key} is turned off for this makerspace."
        super().__init__({"detail": self.message, "code": f"{kind}_disabled", kind: key})

    def __str__(self):
        return self.message


def module_off(module_key, message=None):
    return SurfaceOff("module", canonical_module_key(module_key), message)


def feature_off(feature_key, message=None):
    return SurfaceOff("feature", feature_key, message)


def require_module(makerspace_or_id, module_key):
    makerspace = (
        makerspace_or_id
        if isinstance(makerspace_or_id, Makerspace)
        else get_object_or_404(Makerspace, pk=makerspace_or_id)
    )
    if not module_enabled(makerspace, module_key):
        raise module_off(module_key)
    return makerspace


def require_module_for_servable(makerspace, module_key):
    """Check capability after a canonical servable lookup without querying it twice.

    Public surfaces only: an edition that hides this module answers 404 here, and so
    does a module that is off for this space.
    """
    from apps.makerspaces.editions import require_public_surface

    if not isinstance(makerspace, Makerspace):
        raise TypeError("A servability-checked Makerspace instance is required.")
    module_key = canonical_module_key(module_key)
    require_public_surface(module_key)
    if (
        module_key not in set(canonical_module_keys(makerspace.enabled_modules))
        or not module_available(module_key)
        or not inventory_master_allows(makerspace, module_key)
    ):
        raise module_off(module_key)
    return makerspace


def require_module_locked(makerspace_or_id, module_key):
    """Re-check a module gate while holding the makerspace row lock (plan A8).

    `require_module` at the view boundary reads an unlocked row, so a concurrent
    uninstall can commit in the window between that check and the create -- leaving
    behind a row belonging to a module that is now off. Validating on the disable
    side instead does not help: it loses the same race from the other end.

    Every `module_install` mutation takes `select_for_update` (FOR UPDATE) on the
    makerspace. The FOR NO KEY UPDATE taken here conflicts with that lock, with itself
    and with any UPDATE of the row, so it serializes creators against disablers, exactly
    the way `check_quota` (also NO KEY UPDATE) serializes creators against each other.
    Call this **inside** the creation service's `transaction.atomic()`, next to the quota
    check, so both share one lock mode and one ordering.
    """
    pk = makerspace_or_id.pk if isinstance(makerspace_or_id, Makerspace) else makerspace_or_id
    # NO KEY UPDATE still serializes creators against module installs/uninstalls (it
    # conflicts with FOR UPDATE and itself) but not with the FOR KEY SHARE locks that
    # deferred foreign-key checks take at COMMIT. A plain FOR UPDATE here deadlocked any
    # workflow that commits rows referencing the makerspace while this holder waited on
    # one of that workflow's request rows (device printer apply vs machine-service cancel).
    locked = Makerspace.objects.select_for_update(no_key=True).get(pk=pk)
    if not module_enabled(locked, module_key):
        raise module_off(module_key)
    return locked


def require_feature(makerspace_or_id, feature_key):
    makerspace = (
        makerspace_or_id
        if isinstance(makerspace_or_id, Makerspace)
        else get_object_or_404(Makerspace, pk=makerspace_or_id)
    )
    if not feature_enabled(makerspace, feature_key):
        raise feature_off(feature_key)
    return makerspace


def require_feature_locked(makerspace_or_id, feature_key):
    """Re-check a feature gate while holding the makerspace row lock.

    NO KEY UPDATE for the same reason as `require_module_locked`: feature toggles still
    serialize against it, and callers that take both never upgrade the lock.
    """
    pk = makerspace_or_id.pk if isinstance(makerspace_or_id, Makerspace) else makerspace_or_id
    locked = Makerspace.objects.select_for_update(no_key=True).get(pk=pk)
    if not feature_enabled(locked, feature_key):
        raise feature_off(feature_key)
    return locked
