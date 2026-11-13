"""How the /control/ capability matrix completes a selection (MP-28, owner decisions #82/#87).

The page script and this module apply the same three rules, so a save that bypasses
the script ends where the script would have:

* Ticking a module ticks the modules it requires (transitively).
* Ticking a feature ticks its parent module, every module and feature it
  `requires_*`, and their requirements in turn (LANE-RULES §9, #87).
* Unticking a module that was on unticks every module and feature that needs it, and
  unticking a feature unticks the features built on it; the caller reports what was
  turned off. Nothing is ever silently re-ticked: an untick wins over a still-ticked
  dependant.

Core modules are always on, so unticking one removes nothing.
"""

from dataclasses import dataclass

from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.capability_validation import required_feature_closure
from apps.makerspaces.module_registry import MODULES, core_module_keys, with_dependencies


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


def complete_selection(before_modules, modules, features, before_features=()):
    ticked = set(modules)
    core = core_module_keys()
    unticked = (set(before_modules) - ticked) - core
    # A still-ticked module that needs an unticked one goes with it, or completion
    # would quietly tick the unticked module back.
    cascaded = {key for key in ticked - core if with_dependencies({key}) & unticked}
    removed = unticked | cascaded
    # An unticked feature seeds the cascade like an unticked module: what is built on it
    # goes too, and it is never re-ticked by a dependant that stayed ticked.
    unticked_features = set(before_features) - set(features)
    kept_features, dropped = [], set(unticked_features)
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
    requested = set(kept_features)
    previously_selected = set(before_features)
    # An unchanged default can be dormant. Only an explicit selection may fill
    # in its prerequisites. Keep the choice so enabling a prerequisite wakes it.
    dormant = {
        key for key in requested & previously_selected
        if key in FEATURES and FEATURES[key].default_enabled
        and required_feature_closure({key}) - previously_selected
    }
    closure = required_feature_closure(requested - dormant)
    dormant = {key for key in dormant if feature_needs(key) <= ticked | core}
    kept_features = [key for key in FEATURES if key in closure or key in dormant]
    needed = set()
    for key in closure:
        needed |= feature_needs(key)
    completed = with_dependencies((ticked - cascaded) | needed)
    return Completion(
        modules=sorted(completed),
        features=kept_features,
        added=sorted((completed - ticked - core) | (closure - requested)),
        turned_off_modules=sorted(cascaded),
        turned_off_features=sorted(dropped - unticked_features),
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
