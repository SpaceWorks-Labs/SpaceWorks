"""Shared feature configuration policy and live, batched tenant eligibility."""

from .capabilities import FEATURE_MODULES, FEATURES
from .capability_definitions import RETIRED_FEATURES
from .loan_visibility import LOAN_FEATURES
from .module_aliases import canonical_module_keys
from .module_registry import module_available
from apps.separability.registry import runtime_active


def configuration_feature_enabled(makerspace, key):
    """Evaluate loaded configuration only; callers must separately check servability."""
    if key in RETIRED_FEATURES:
        return False
    if key in LOAN_FEATURES and not configuration_feature_enabled(makerspace, "loans.enabled"):
        return False
    definition = FEATURES.get(key)
    if definition is None or key not in set(makerspace.enabled_features or []):
        return False
    if definition.parent_module is not None and definition.parent_module not in FEATURE_MODULES:
        return False
    if definition.app_label is not None and not runtime_active(definition.app_label):
        return False
    # A stored retired key (e.g. `printing`) still reads as the module it folded into (decision 340b).
    modules = set(canonical_module_keys(makerspace.enabled_modules))
    required_modules = (
        module for module in (definition.parent_module, *definition.requires_modules)
        if module is not None
    )
    return all(module in modules and module_available(module) for module in required_modules) and all(
        configuration_feature_enabled(makerspace, feature) for feature in definition.requires_features
    )


def unavailable_features(keys):
    """Keys that can never read on in this deployment: retired, or their app/module is not shipped.

    A switch turned ON for one of these would be stored, report success and change nothing, the
    same dead capability `module_install.install_module` refuses for a module. Callers refuse
    only the keys a request newly turns on: a deployment-level decision never rewrites what a
    tenant already stored (uninstall and tombstoning are both reversible).
    """
    out = []
    for key in keys:
        definition = FEATURES.get(key)
        if definition is None:
            continue
        required = (definition.parent_module, *definition.requires_modules)
        if (key in RETIRED_FEATURES
                or (definition.app_label is not None and not runtime_active(definition.app_label))
                or any(module is not None and not module_available(module) for module in required)):
            out.append(key)
    return sorted(out)


def feature_enabled_servable_ids(makerspace_ids, key):
    """Resolve fresh tenant configuration and recovery exclusions in one query.

    No result is cached on a user/session. Both single-tenant and discovery paths
    use the same configuration policy; SQL applies the live servability policy.
    """
    from .models import Makerspace
    from .servability import servable_queryset

    rows = servable_queryset(Makerspace.objects.filter(pk__in=makerspace_ids)).only(
        "enabled_modules", "enabled_features",
    )
    return {row.pk for row in rows if configuration_feature_enabled(row, key)}
