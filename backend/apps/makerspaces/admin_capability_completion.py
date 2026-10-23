"""How the /control/ capability matrix completes a selection (MP-28, owner decisions #82/#87).

The page script and this module apply the same three rules, so a save that bypasses
the script ends where the script would have:

* Ticking a module ticks the modules it requires (transitively).
* Ticking a feature ticks its parent module and that module's requirements.
* Unticking a module that was on unticks every module and feature that needs it,
  and the caller reports what was turned off. Nothing is ever silently re-ticked:
  an untick wins over a still-ticked dependant.

A feature's other declared requirements (`requires_modules`, `requires_features`) are
not inferred when ticking; `validate_capabilities` still refuses a selection missing them.
Core modules are always on, so unticking one removes nothing.
"""

from dataclasses import dataclass

from apps.makerspaces.capabilities import FEATURE_DEFINITIONS
from apps.makerspaces.module_registry import MODULES, core_module_keys, with_dependencies

FEATURES = {item.key: item for item in FEATURE_DEFINITIONS}


def feature_needs(key):
    """Every module a feature cannot work without: parent, declared modules, their closures."""
    item = FEATURES[key]
    return with_dependencies({m for m in (item.parent_module, *item.requires_modules) if m})


@dataclass(frozen=True)
class Completion:
    modules: list
    features: list
    added: list
    turned_off_modules: list
    turned_off_features: list


def complete_selection(before_modules, modules, features):
    ticked = set(modules)
    core = core_module_keys()
    unticked = (set(before_modules) - ticked) - core
    # A still-ticked module that needs an unticked one goes with it, or completion
    # would quietly tick the unticked module back.
    cascaded = {key for key in ticked - core if with_dependencies({key}) & unticked}
    removed = unticked | cascaded
    kept_features, dropped = [], set()
    for key in features:
        if key in FEATURES and feature_needs(key) & removed:
            dropped.add(key)
        else:
            kept_features.append(key)
    changed = True
    while changed:  # a feature built on a dropped feature is dropped too
        changed = False
        for key in list(kept_features):
            if key in FEATURES and set(FEATURES[key].requires_features) & dropped:
                kept_features.remove(key)
                dropped.add(key)
                changed = True
    parents = {FEATURES[key].parent_module for key in kept_features if key in FEATURES}
    completed = with_dependencies((ticked - cascaded) | {p for p in parents if p})
    return Completion(
        modules=sorted(completed),
        features=kept_features,
        added=sorted(completed - ticked - core),
        turned_off_modules=sorted(cascaded),
        turned_off_features=sorted(dropped),
    )


def matrix_rules():
    """The same rules as data for the page script, keyed by checkbox value."""
    return {
        "modules": {
            f"module:{item.key}": {
                "requires": sorted(f"module:{key}" for key in with_dependencies({item.key}) - {item.key}),
                "core": item.is_core,
            }
            for item in MODULES
        },
        "features": {
            f"feature:{key}": {
                "parent": f"module:{item.parent_module}" if item.parent_module else None,
                "needs": sorted(f"module:{module}" for module in feature_needs(key)),
                "requires_features": [f"feature:{other}" for other in item.requires_features],
            }
            for key, item in FEATURES.items()
        },
    }
