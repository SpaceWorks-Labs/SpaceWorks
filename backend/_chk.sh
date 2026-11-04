pip install -q --no-cache-dir -r requirements.txt >/dev/null 2>&1 || true
python manage.py shell -c "
def run(name, fn):
    try:
        r = fn(); print(name, 'ok', r if isinstance(r, (int, str)) else '')
    except Exception as exc:
        print(name, 'FAIL', str(exc)[:1500])
from apps.tenant_migration.tenant_dump_catalog import schema_digest, CATALOG_SCHEMA_SHA256 as P
run('DIGEST', lambda: schema_digest() + (' MATCH' if schema_digest()==P else ' DIFF'))
from apps.tenant_migration.projection_guards import validate_projection_registry
run('PROJ', validate_projection_registry)
from apps.audit.presentation_guards import presentation_catalog_errors as e
run('PRES', lambda: ('0' if not e() else str(e()[:15])))
from apps.tenant_migration.audit_reference_guards import validate_audit_meta_references as v
run('AREF', lambda: len(v().actions))
from apps.tenant_migration.source_gate_guards import validate_source_gate_coverage
run('GATE', validate_source_gate_coverage)
from apps.tenant_rls.policies import build_plans
run('RLS', lambda: str(build_plans()[1] or 'none unresolved'))
from apps.makerspaces.capability_definitions import FEATURE_DEFINITIONS as F
run('FEATS', lambda: len(F))
" 2>&1 | grep -E "^(DIGEST|PROJ|PRES|AREF|GATE|RLS|FEATS)|Traceback"
python manage.py check 2>&1 | grep -v "INFO\|WARNING apps.tenant_migration" | tail -6
python manage.py makemigrations --check --dry-run 2>&1 | tail -3
