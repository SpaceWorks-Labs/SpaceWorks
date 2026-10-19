"""Derive raw insertion order from the live exported model graph."""

from apps.data_export.models import EXPORTED_MODELS

from .insertion_errors import DependencyCycleError


def concrete_fk_dependencies(models, *, include_nullable=True):
    """Return model -> exported concrete FK targets, excluding legitimate self-FKs."""
    by_label = {model._meta.label: model for model in models}
    dependencies = {label: set() for label in by_label}
    for label, model in by_label.items():
        for field in model._meta.local_concrete_fields:
            if not field.is_relation or field.related_model is None:
                continue
            if not include_nullable and getattr(field, "null", False):
                continue
            target = field.related_model._meta.label
            if target in by_label and target != label:
                dependencies[label].add(target)
    return dependencies


def topologically_sort_models(models):
    """Place each referenced model before its referrers and name any cycle.

    PKs are preallocated for every model before any insert and FK constraints are
    deferred, so a nullable pointer (for example a "current" row) may close a
    cycle: its members are released once only nullable dependencies remain unmet.
    A cycle through required FKs is still refused.
    """
    by_label = {model._meta.label: model for model in models}
    remaining = concrete_fk_dependencies(models)
    required = concrete_fk_dependencies(models, include_nullable=False)
    ordered = []
    while remaining:
        ready = [label for label, targets in remaining.items() if not targets]
        if not ready:
            ready = [label for label, targets in remaining.items() if not targets & required[label]]
        if not ready:
            raise DependencyCycleError(
                "Concrete-FK dependency cycle: " + ", ".join(sorted(remaining))
            )
        label = min(ready)
        ordered.append(by_label[label])
        del remaining[label]
        for targets in remaining.values():
            targets.discard(label)
    return ordered


def exported_models_in_dependency_order(apps_registry):
    return topologically_sort_models(
        [apps_registry.get_model(label) for label in EXPORTED_MODELS]
    )
