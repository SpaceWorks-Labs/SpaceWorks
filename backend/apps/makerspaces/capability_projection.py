"""Read-only capability projection after a canonical servable-space query.

Mutation/authorization paths must keep using platform.feature_enabled. Callers
here must supply spaces freshly loaded through servable_queryset in this response.
This avoids re-reading restoration state for every projected field and row.
"""

from .capabilities import FEATURES, FEATURE_MODULES
from .loan_visibility import LOAN_FEATURES
from .module_registry import module_available
from apps.separability.registry import runtime_active


def feature_flags_for_servable(makerspace, keys):
    modules = set(makerspace.enabled_modules or [])
    enabled = set(makerspace.enabled_features or [])
    cache = {}

    def effective(key):
        if key in cache:
            return cache[key]
        definition = FEATURES.get(key)
        if definition is None or key not in enabled:
            return False
        if definition.parent_module is not None and definition.parent_module not in FEATURE_MODULES:
            return False
        if definition.app_label is not None and not runtime_active(definition.app_label):
            return False
        required = (definition.parent_module, *definition.requires_modules)
        cache[key] = all(
            module in modules and module_available(module)
            for module in required if module is not None
        ) and all(effective(feature) for feature in definition.requires_features)
        if key in LOAN_FEATURES:
            cache[key] = cache[key] and effective("loans.enabled")
        return cache[key]

    return {key: effective(key) for key in keys}
