"""Fresh and collision-protected unique values for import rows (split from `row_planning`).

Re-exported from ``row_planning``; import them from there.
"""

from .omitted_fields import OMITTED_FIELD_RECONSTRUCTIONS, OmittedFieldDisposition
from .unique_values import collision_policy


def _reconstructed_value(label, field, fresh_values):
    disposition = OMITTED_FIELD_RECONSTRUCTIONS[(label, field.name)]
    if label in {"events.SubmissionAsset", "events.HackathonParticipantAsset"} and field.name in {"staging_key", "verification_key"}:
        return _fresh_unique(field, fresh_values)
    if disposition is OmittedFieldDisposition.FRESH:
        value = _fresh_unique(field, fresh_values)
    elif disposition is OmittedFieldDisposition.EMPTY_STRING:
        value = ""
    elif disposition is OmittedFieldDisposition.NULL:
        value = None
    elif disposition is OmittedFieldDisposition.DERIVED:
        value = field.get_default() if field.has_default() else None
    elif disposition is OmittedFieldDisposition.DROP_ROW:
        value = ""
    else:
        raise ValueError(f"Unsupported omitted-field disposition for {label}.{field.name}.")
    return value


def _fresh_unique(field, fresh_values, generator=None):
    key = (field.model._meta.label, field.name)
    current_batch = fresh_values.setdefault(key, set())
    if field.model._meta.label in {"events.SubmissionAsset", "events.HackathonParticipantAsset"} and field.name in {"staging_key", "verification_key"}:
        from uuid import uuid4
        generate = lambda: f"import-coordination/{uuid4()}/{field.name}"
    else:
        generate = generator or field.get_default
    for _attempt in range(16):
        value = generate()
        if value in current_batch:
            continue
        if field.model._base_manager.filter(**{field.name: value}).exists():
            continue
        current_batch.add(value)
        return value
    raise RuntimeError(f"Could not generate a unique value for {key[0]}.{key[1]}.")


def protect_carried_unique_values(model, row, target, fresh_values):
    """Preserve carried labels/keys, changing only a value that actually collides."""
    outcomes = []
    label = model._meta.label
    for field in model._meta.local_concrete_fields:
        policy = collision_policy(label, field.name)
        if policy is None:
            continue
        value = row[field.column]
        if value is None:
            # NULL never violates a unique constraint; there is no identity to preserve.
            continue
        key = (label, field.name)
        current_batch = fresh_values.setdefault(key, set())
        collision = value in current_batch or model._base_manager.filter(
            **{field.name: value}
        ).exists()
        if collision:
            generator = (
                (lambda: policy.generator(row, target, value))
                if policy.generator is not None
                else field.get_default
            )
            row[field.column] = _fresh_unique(field, fresh_values, generator)
            outcomes.append((field.name, "regenerated"))
        else:
            current_batch.add(value)
            outcomes.append((field.name, "preserved"))
    return outcomes
