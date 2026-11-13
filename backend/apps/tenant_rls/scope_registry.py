"""Which tables are makerspace-scoped, read from the classification (never a hand list).

The source of truth is the ownership predicate each table already declares for
per-space backup slices (``backup.slice_rows.SLICE_ROW_SPECS``: every data_export
dataset plus the staff credentials a lossless slice carries). Any other model with a
concrete foreign key to the makerspace is scoped through that key. So a lane that adds
a classified model is covered by the next ``migrate`` with nothing else to do.

``EXEMPT`` is the closed list of makerspace-owned models that are deliberately not
policed, each with its reason; ``tests/tenant_rls/test_policies_generated.py`` pins it.
"""

from django.apps import apps

from apps.data_export.types import TenantPredicate

ROOT = "makerspaces.Makerspace"

EXEMPT = {
    ROOT: (
        "The tenant root: every space's directory row, servability and lifecycle are read "
        "platform-wide (rbac, origin scoping, the public directory). Its children carry the policy."
    ),
    "tenant_rls.FixedRoleScope": (
        "The L25 role-to-space map read by the SECURITY DEFINER policy function; operator-managed."
    ),
}


def _direct_paths(model):
    return tuple(
        field.name for field in model._meta.local_concrete_fields
        if field.is_relation and (field.many_to_one or field.one_to_one)
        and field.related_model is not None and field.related_model._meta.label == ROOT
    )


def predicates():
    """label -> TenantPredicate for every policed model."""
    from apps.backup.slice_rows import SLICE_ROW_SPECS

    result = {}
    for model in apps.get_models():
        meta = model._meta
        if meta.proxy or not meta.managed or meta.label in EXEMPT:
            continue
        spec = SLICE_ROW_SPECS.get(meta.label)
        if spec is not None:
            result[meta.label] = spec[1]
            continue
        direct = _direct_paths(model)
        if direct:
            result[meta.label] = TenantPredicate(direct)
    return result
