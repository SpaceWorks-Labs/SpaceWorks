"""Shared feature configuration policy and live, batched tenant eligibility."""

from .capabilities import FEATURE_MODULES, FEATURES
from .loan_visibility import LOAN_FEATURES
from .module_registry import module_available


def configuration_feature_enabled(makerspace, key):
    """Evaluate loaded configuration only; callers must separately check servability."""
    if key in LOAN_FEATURES and not configuration_feature_enabled(makerspace, "loans.enabled"):
        return False
    definition = FEATURES.get(key)
    if definition is None or key not in set(makerspace.enabled_features or []):
        return False
    if definition.parent_module is not None and definition.parent_module not in FEATURE_MODULES:
        return False
    modules = set(makerspace.enabled_modules or [])
    required_modules = (
        module for module in (definition.parent_module, *definition.requires_modules)
        if module is not None
    )
    return all(module in modules and module_available(module) for module in required_modules) and all(
        configuration_feature_enabled(makerspace, feature) for feature in definition.requires_features
    )


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
