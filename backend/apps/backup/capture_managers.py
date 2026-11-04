"""The manager a whole-tenant capture, restore, migration or export reads rows through.

Most models' default manager returns every stored row, but not all. Since one account
per person (U-A1), ``MakerspaceMembership.objects`` returns COMMUNITY rows only, so a
generic ``model.objects`` loop over the tenant's datasets silently dropped every
staff-track row: a per-space archive lost the space's staff, and restoring it then deleted
them. Code in ``backup``, ``tenant_migration``, ``data_export`` and ``separability`` that
reads a model it did not name explicitly goes through :func:`every_row` instead
(guard: ``tests/backup/test_capture_manager_guard.py``).

``_base_manager`` would also see every row, but it drops a model's custom queryset (the
append-only and PII-update refusals some models install), so the default manager is kept
wherever it is not filtered. A new filtered default manager must be listed here; the
guard refuses the build until it is.
"""

# label -> the unfiltered manager of a model whose DEFAULT manager hides rows.
FILTERED_DEFAULT_MANAGERS = {
    "makerspaces.MakerspaceMembership": "all_tracks",
}


def every_row(model):
    """A manager over every stored row of ``model``: both membership tracks, for example."""
    name = FILTERED_DEFAULT_MANAGERS.get(model._meta.label)
    return getattr(model, name) if name else model._default_manager
