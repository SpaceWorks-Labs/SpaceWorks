"""Run only source-AST audit discovery without importing Django on this host."""
import ast
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[3]
ns = {'ast': ast, 'dataclass': dataclass, 'Path': Path,
      'apps': SimpleNamespace(__file__=str(root / 'backend/apps/__init__.py')),
      'AUDIT_META_REFERENCES': {}}
for name in ('tenant_migration/audit_reference_guards.py', 'audit/presentation_discovery.py'):
    path = root / 'backend/apps' / name
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    exec(compile(tree, str(path), 'exec'), ns)
sites = ns['discover_dynamic_audit_sites']()
discovery = ns['discover_audit_meta_references']()
policy = {}
exec((root / 'backend/apps/audit/presentation_catalog_dynamic.py').read_text(), policy)
errors = []
for kind, key in (('exact', 'DYNAMIC_EXACT_ACTIONS'), ('non_literal_meta', 'NON_LITERAL_META_ACTIONS')):
    actual = {action for site in sites if site.kind == kind for action in site.actions}
    if actual != set(policy[key]): errors.append((key, sorted(actual ^ set(policy[key]))))
wrappers = {site.path for site in sites if site.kind == 'wrapper'}
if wrappers != set(policy['WRAPPER_SITE_PREFIXES']):
    errors.append(('wrappers', sorted(wrappers ^ set(policy['WRAPPER_SITE_PREFIXES']))))
entries = {}
def P(action, label, permitted=(), *args, **kwargs):
    if action in entries: errors.append(('duplicate', action))
    entries[action] = permitted
for path in (root / 'backend/apps/audit').glob('presentation_catalog_*.py'):
    for node in ast.parse(path.read_text(encoding='utf-8-sig')).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ENTRIES' for t in node.targets):
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), {'P': P})
missing = discovery.actions - set(entries)
if missing: errors.append(('missing literal actions', sorted(missing)))
known = discovery.actions | {action for site in sites if site.kind == 'exact' for action in site.actions}
if set(entries) - known: errors.append(('stale literal actions', sorted(set(entries) - known)))
for action, allowed in entries.items():
    for path in allowed:
        if (action, path) not in discovery.meta_paths: errors.append(('missing leaf', action, path))
        if policy['is_denied'](action): errors.append(('denied leaf', action, path))
for error in errors: print(error)
assert not errors, 'Audit AST drift found'
print(f'Audit AST coverage PASS: {len(discovery.actions)} literal actions; {len(sites)} dynamic sites')
