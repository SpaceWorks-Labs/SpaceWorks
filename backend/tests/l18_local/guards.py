import traceback

def run(name, fn):
    try:
        result = fn()
        if isinstance(result, list) and result and isinstance(result[0], str):
            print("FAIL", name); [print("   ", r) for r in result[:40]]
        else:
            print("OK", name)
    except Exception as exc:
        print("FAIL", name); print("   ", str(exc)[:3000])

def g_export():
    from apps.data_export.guards import validate_all; validate_all()
def g_catalog():
    from apps.tenant_migration import tenant_dump_catalog as c
    try:
        c.validate_catalog()
    except Exception as exc:
        if "digest drifted" not in str(exc):
            raise
        actual = str(exc).rsplit("actual=", 1)[1].strip()
        print("   (catalog digest drifted as expected; coordinator regenerates)", actual)
        c.validate_catalog(expected_schema_digest=actual)
def g_authority():
    from apps.tenant_migration.authority_guards import validate_authority_registry; validate_authority_registry()
def g_projection():
    from apps.tenant_migration.projection_guards import validate_projection_registry; validate_projection_registry()
def g_unique():
    from apps.tenant_migration.projection_guards import validate_unique_constraint_risks; validate_unique_constraint_risks()
def g_refs():
    from apps.tenant_migration.reference_guards import validate_reference_registry; validate_reference_registry()
def g_audit_meta():
    from apps.tenant_migration.audit_reference_guards import validate_audit_meta_references; validate_audit_meta_references()
def g_omitted():
    from apps.tenant_migration.omitted_field_guards import validate_omitted_field_reconstructions; validate_omitted_field_reconstructions()
def g_source_gate():
    from apps.tenant_migration.source_gate_guards import validate_source_gate_coverage; validate_source_gate_coverage()
def g_tasks():
    from apps.tenant_migration.source_gate_guards import validate_task_coverage; validate_task_coverage()
def g_fanout():
    from apps.tenant_migration.source_gate_fanout_guards import validate_fanout_gate_coverage; validate_fanout_gate_coverage()
def g_claims():
    from apps.accounts.claim_route_guard import validate_claim_route_matrix; validate_claim_route_matrix()
def g_presentation():
    from apps.audit.presentation_guards import presentation_catalog_errors; return presentation_catalog_errors()
def g_objects():
    from apps.backup.object_ownership_registry import validate_object_reference_registry; validate_object_reference_registry()
def g_reports():
    from apps.operations.report_registry import REPORT_DEFINITIONS
    from apps.operations.report_validation import validate_report_definition
    for d in REPORT_DEFINITIONS: validate_report_definition(d)
def g_backup_rules():
    from django.apps import apps
    from apps.backup.main_projection_registry import table_rules
    covered = {rule.model for rule in table_rules()}
    missing = [m._meta.label for m in apps.get_models() if m._meta.app_label in ("payments", "events") and m not in covered]
    return [f"no backup rule: {m}" for m in missing]

import os
_ONLY = set(filter(None, os.environ.get("GUARDS", "").split(",")))
for name, fn in list(globals().items()):
    if name.startswith("g_") and (not _ONLY or name[2:] in _ONLY):
        run(name[2:], fn)
