"""Not collected by default (no test_ prefix). Throwaway integration diagnostics.

    ./scripts/dev.sh test tests/fixed_roles/gen_integration_dump.py -q
"""

import io
import pprint
from pathlib import Path

import pytest
from django.core.management import call_command

OUT = Path("/workspace/backend/tests/.junit")


def _write(name, text):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(text)


@pytest.mark.django_db
def test_dump_everything():
    lines = []
    # Authority matrix
    from apps.tenant_migration.tenant_dump_authority import AUTHORITY_FIELD_OVERRIDES
    from tests.tenant_migration.authority_expectations_d8 import EXPECTED
    lines.append("== authority: in code, not expected")
    for edge in sorted(set(AUTHORITY_FIELD_OVERRIDES) - set(EXPECTED)):
        rule = AUTHORITY_FIELD_OVERRIDES[edge]
        lines.append(f"{edge!r}: {getattr(rule, 'dispositions', rule)!r}")
    lines.append("== authority: expected, not in code")
    for edge in sorted(set(EXPECTED) - set(AUTHORITY_FIELD_OVERRIDES)):
        lines.append(repr(edge))
    # Target projection
    from apps.tenant_migration.target_projection import TARGET_FIELD_PROJECTION
    from tests.tenant_migration.target_projection_expectations import EXPECTED_TARGET_VALUES
    lines.append("== target projection: in code, not expected")
    for edge in sorted(set(TARGET_FIELD_PROJECTION) - set(EXPECTED_TARGET_VALUES)):
        policy = TARGET_FIELD_PROJECTION[edge]
        try:
            value = policy.resolved_value(*edge)
        except Exception as exc:  # noqa: BLE001
            value = f"<error {exc!r}>"
        lines.append(f"{edge!r}: value={value!r} default={policy.use_model_default!r} "
                     f"resolver={getattr(policy, 'resolver', None)!r} cond={getattr(policy, 'condition', None)!r}")
    lines.append("== target projection: expected, not in code")
    for edge in sorted(set(EXPECTED_TARGET_VALUES) - set(TARGET_FIELD_PROJECTION)):
        lines.append(repr(edge))
    # Scope registry
    from apps.apiclients.scope_registry import SCOPE_REGISTRY
    lines.append("== scope registry: excluded from legacy:v1")
    for key in sorted(k for k, e in SCOPE_REGISTRY.items() if not e.legacy_v1):
        lines.append(repr(key))
    # Presentation guard
    from apps.audit.presentation_guards import presentation_catalog_errors
    lines.append("== presentation errors")
    lines.extend(presentation_catalog_errors())
    from apps.audit.presentation_discovery import discover_dynamic_audit_sites
    from apps.audit.presentation_catalog import DYNAMIC_EXACT_ACTIONS, NON_LITERAL_META_ACTIONS
    for site in discover_dynamic_audit_sites():
        hit = set(site.actions) & {"api_client.created", "api_client.updated"}
        if hit or (site.kind == "exact" and not set(site.actions) <= DYNAMIC_EXACT_ACTIONS) or (
            site.kind == "non_literal_meta" and not set(site.actions) <= NON_LITERAL_META_ACTIONS
        ):
            lines.append(f"site: {site!r}")
    # Migration state vs model
    from django.apps import apps
    from django.db.migrations.loader import MigrationLoader
    from django.db import connection
    loader = MigrationLoader(connection)
    state = loader.project_state()
    old = state.models[("makerspaces", "makerspace")].fields["enabled_modules"]
    new = apps.get_model("makerspaces", "Makerspace")._meta.get_field("enabled_modules")
    lines.append("== enabled_modules state deconstruct")
    lines.append(pprint.pformat(old.deconstruct()))
    lines.append("== enabled_modules model deconstruct")
    lines.append(pprint.pformat(new.deconstruct()))
    _write("integ_dump.txt", "\n".join(str(line) for line in lines) + "\n")
