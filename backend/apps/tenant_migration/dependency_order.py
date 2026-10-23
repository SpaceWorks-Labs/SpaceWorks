"""Derive raw insertion order from the live exported model graph."""

from apps.data_export.models import EXPORTED_MODELS

from .insertion_errors import DependencyCycleError

# Non-FK references that an insert trigger checks immediately (FKs are deferred).
# A stage form's revision rows name it by selector_id, and the selector guard needs
# the stage form row to exist first.
SEMANTIC_DEPENDENCIES = {"events.EventFormRevision": frozenset({"events.EventStageForm"})}


def concrete_fk_dependencies(models, *, include_nullable=True):
    """Return concrete FK dependencies plus finalized-consumption source dependencies."""
    by_label = {model._meta.label: model for model in models}
    dependencies = {label: set() for label in by_label}
    for label, model in by_label.items():
        for field in model._meta.local_concrete_fields:
            from .page_pointer_fixups import PAGE_POINTERS, deferred_pointer
            if (label, field.name) in PAGE_POINTERS and deferred_pointer(field):
                continue
            if not field.is_relation or field.related_model is None:
                continue
            if not include_nullable and getattr(field, "null", False):
                continue
            target = field.related_model._meta.label
            if target in by_label and target != label:
                dependencies[label].add(target)
    if "machines.ConsumableCostRecord" in dependencies:
        from .tracking_references import COST_SOURCE_MODELS
        dependencies["machines.ConsumableCostRecord"].update(set(COST_SOURCE_MODELS.values()) & by_label.keys())
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
    for label, targets in SEMANTIC_DEPENDENCIES.items():
        if label in by_label:
            present = targets & by_label.keys()
            remaining[label] |= present
            required[label] |= present
    ordered = []
    while remaining:
        ready = [label for label, targets in remaining.items() if not targets]
        if not ready:
            ready = [label for label, targets in remaining.items() if not targets & required[label]]
            # Release a member of the actual cycle, never an acyclic row that merely waits on
            # it: insert triggers may check a nullable pointer's row exists.
            cyclic = [label for label in ready if _reaches(label, remaining)]
            ready = cyclic or ready
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


def _reaches(start, remaining):
    seen, stack = set(), list(remaining[start])
    while stack:
        label = stack.pop()
        if label == start:
            return True
        if label in seen or label not in remaining:
            continue
        seen.add(label)
        stack.extend(remaining[label])
    return False


def exported_models_in_dependency_order(apps_registry):
    return topologically_sort_models(
        [apps_registry.get_model(label) for label in EXPORTED_MODELS]
    )
