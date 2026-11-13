"""makerspaces/0154: fold the retired `printing` module key into `machine_service` (decision 340b).

Machine service takes service requests for every machine type, so the 3D print queue is one
machine type inside it rather than a module of its own. Every space keeps what it had:

* `printing` installed -> `printing` is stripped and `machine_service` is on (it already was
  wherever the registry's old `printing -> machine_service` dependency held);
* spaces without `printing` are not touched -- in particular `machine_service` is never
  switched on for a space that did not have printing;
* no row of any other table is touched; one `makerspace.module_retired` audit row per space.

Reversible. The audit row records whether this migration had to ADD `machine_service`, so
the reverse puts back exactly the pre-upgrade module list: `printing` returns, and
`machine_service` is removed again only where this migration was the one that added it.

Kept outside `migrations/` so the audit drift guards read its literal action and meta, as
for 0111 and 0119. Historical models only; the keys are frozen copies on purpose.
"""

from apps.makerspaces.migration_support.fixed_roles_audit import record

RETIRED = "printing"
LIVE = "machine_service"
SOURCE = "migration:makerspaces.0154"
ACTION = "makerspace.module_retired"
MODELS = ("makerspaces.Makerspace", "audit.AuditLog", "audit.AuditMacKey")


def _models(apps):
    return {label: apps.get_model(label) for label in MODELS}


def forwards(apps, schema_editor):
    alias = schema_editor.connection.alias
    models = _models(apps)
    Makerspace = models["makerspaces.Makerspace"]
    for space in Makerspace.objects.using(alias).only("pk", "enabled_modules").order_by("pk").iterator():
        modules = list(space.enabled_modules or [])
        if RETIRED not in modules:
            continue
        added = [] if LIVE in modules else [LIVE]
        space.enabled_modules = sorted((set(modules) - {RETIRED}) | {LIVE})
        space.save(using=alias, update_fields=["enabled_modules"])
        record(space.pk, "makerspace.module_retired", "makerspaces.makerspace", space.pk,
               models=models, alias=alias,
               meta={"module": RETIRED, "folded_into": LIVE, "added_modules": added,
                     "capabilities": [], "source": SOURCE})


def backwards(apps, schema_editor):
    """Put `printing` back on every space this migration folded, newest audit row first."""
    alias = schema_editor.connection.alias
    models = _models(apps)
    Makerspace, AuditLog = models["makerspaces.Makerspace"], models["audit.AuditLog"]
    latest = {}
    rows = AuditLog.objects.using(alias).filter(action=ACTION, meta__source=SOURCE).order_by("-pk")
    for row in rows.only("pk", "makerspace_id", "meta").iterator():
        latest.setdefault(row.makerspace_id, row.meta or {})
    for space in Makerspace.objects.using(alias).filter(pk__in=list(latest)).only("pk", "enabled_modules"):
        modules = set(space.enabled_modules or [])
        restored = (modules | {RETIRED}) - set(latest[space.pk].get("added_modules") or [])
        if restored != modules:
            space.enabled_modules = sorted(restored)
            space.save(using=alias, update_fields=["enabled_modules"])
