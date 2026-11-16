"""Who switched a module or feature, at which level, from what to what (module audit 0.12.0).

Every per-space switch writes `makerspace.capabilities_changed` (modules, from the module
service and `/control/`) or `makerspace.features_changed` (features, from every writer that
can flip one). Both carry the same context so an auditor can answer the three questions
without guessing from the actor's current roles:

* ``scope``     -- always ``"space"``: these rows change one makerspace. The deployment level
  (`TOMBSTONED_APPS`, `SPACEWORKS_EDITION`, `HUB_LANDING_ENABLED`) is environment read at
  start-up; nothing at runtime writes it, so it has no audit row and is shown read-only.
* ``authority`` -- ``"platform"`` when a platform superadmin acted, ``"space"`` for space staff,
  ``"system"`` when no person did (setup, migrations, scheduled work).
* ``via``       -- the surface that made the change (``console``, ``control``, ``cli``, ...).

``before``/``after`` stay where they always were; this only adds keys, so readers that pick
fields out of the meta keep working.
"""

from apps.audit import services as audit


def switch_context(actor, via):
    from apps.accounts.platform_authority import is_platform_superadmin

    if actor is None or not getattr(actor, "is_authenticated", False):
        authority = "system"
    elif is_platform_superadmin(actor):
        authority = "platform"
    else:
        authority = "space"
    return {"scope": "space", "authority": authority, "via": via}


def record_features_changed(actor, makerspace, before, after, *, via):
    """Audit a feature switch change; a no-op when nothing changed."""
    before, after = sorted(set(before or [])), sorted(set(after or []))
    if before == after:
        return None
    context = switch_context(actor, via)
    # A literal dict (no `**` spread) so the audit presentation can show these keys.
    return audit.record(
        actor, "makerspace.features_changed", makerspace=makerspace, target=makerspace,
        meta={"before": before, "after": after,
              "turned_on": sorted(set(after) - set(before)), "turned_off": sorted(set(before) - set(after)),
              "scope": context["scope"], "authority": context["authority"], "via": context["via"]},
    )
