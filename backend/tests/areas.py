"""Area ownership for collection, local selectors and coverage audits (no Django setup).

Paths are relative to backend/. Imports and literal module/feature keys add owners;
they never replace path ownership. Shared tests deliberately belong to several areas.
"""
import argparse
import ast
from dataclasses import dataclass
from fnmatch import fnmatchcase
from functools import lru_cache
from pathlib import Path
import re
import subprocess
import sys

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from apps.makerspaces.module_registry import MODULES  # noqa: E402


@dataclass(frozen=True)
class Area:
    paths: tuple[str, ...]
    apps: tuple[str, ...] = ()


# Core ownership also covers folded capabilities and shared infrastructure apps.
AREAS = {
    "auth": Area(("tests/accounts/**", "tests/account_split/**", "tests/fixed_roles/**",
                  "tests/apiclients/**", "tests/test_auth*.py", "tests/test_*password*.py",
                  "tests/test_rbac*.py", "tests/test_*social*.py", "tests/levels/**",
                  "tests/test_throttle_proxy.py", "tests/test_setup_station_secret.py"), ("accounts", "apiclients")),
    "tenancy": Area(("tests/tenant_rls/**", "tests/encryption/**", "tests/scope_hardening/**",
                     "tests/separability/**", "tests/tombstone/**"), ("tenant_rls", "encryption", "separability")),
    "inventory": Area(("tests/inventory/**", "tests/maintenance/**", "tests/procurement/**",
                       "tests/warranty/**", "tests/test_*inventory*.py", "tests/test_stock*.py"),
                      ("inventory", "maintenance", "procurement", "warranty")),
    "lending": Area(("tests/hardware_requests/**", "tests/evidence/**", "tests/test_*loan*.py",
                     "tests/test_*request*.py", "tests/test_*return*.py", "tests/test_*issue*.py",
                     "tests/test_*box*.py", "tests/test_*qr*.py", "tests/test_*evidence*.py"),
                    ("hardware_requests", "evidence", "boxes")),
    "audit": Area(("tests/audit/**", "tests/test_audit*.py"), ("audit",)),
    "payments_ledger": Area(("tests/payments/**", "tests/billing_docs/**", "tests/money_modes/**",
                             "tests/hackmoney_local/**", "tests/test_reports_ledger.py"), ("payments",)),
    "data_export": Area(("tests/data_export/**",), ("data_export",)),
    "backup": Area(("tests/backup/**",), ("backup",)),
    "tenant_migration": Area(("tests/tenant_migration/**",), ("tenant_migration",)),
    "platform": Area(("tests/cloud/**", "tests/config/**", "tests/docs/**", "tests/deep_migrations/**",
                      "tests/control_restructure_local/**", "tests/hosting_requests/**",
                      "tests/platform_overview_local/**", "tests/r2_superadmin_local/**",
                      "tests/test_*host*.py", "tests/test_*deploy*.py", "tests/test_*release*.py",
                      "tests/test_*control*.py", "tests/test_*platform*.py", "tests/test_*docker*.py",
                      "tests/test_*installer*.py", "tests/test_*environment*.py", "tests/test_*env_*.py",
                      "tests/test_*version*.py", "tests/test_*script*.py", "tests/test_*cron*.py",
                      "tests/test_*redis*.py", "tests/test_*compose*.py", "tests/test_*ghcr*.py",
                      "tests/test_*probe*.py", "tests/_diag/**", "tests/r2_tidy_local/test_check_*.py",
                      "tests/r4_local/test_check_deploy.py", "tests/r4_local/test_edge_headers.py",
                      "tests/l1_local/test_migration_diff.py", "tests/test_object_storage.py",
                      "tests/test_org_rename_migration.py"),
                     ("managed_hosting", "hosting_requests", "space_controls", "storage_capabilities")),
    "api_contract": Area(("tests/api_r2/**", "tests/adapter_conformance/**", "tests/completeness/**", "tests/modules/**",
                          "tests/parity_0120/**", "tests/test_*openapi*.py", "tests/test_*contract*.py",
                          "tests/test_phase9_code_quality.py", "tests/test_areas*.py",
                          "tests/l1_local/test_generate_openapi.py"), ("openapi_contract",)),
    "frontend_shell": Area(("tests/i18n/**", "tests/test_frontend*.py", "tests/test_*theme*.py")),
    "organizations": Area(("tests/organizations/**", "tests/governance/**"), ("organizations",)),
    "forms": Area(("tests/forms_schema/**",), ("forms_schema",)),
}
for module in MODULES:
    derived = Area((f"tests/{module.app_label}/**", f"tests/test_{module.key}*.py",
                    "tests/modules/test_switch_matrix_contract.py",
                    "tests/modules/test_switch_matrix_snapshot_guard.py"), (module.app_label,))
    prior = AREAS.get(module.key, Area(()))
    AREAS[module.key] = Area(prior.paths + derived.paths, prior.apps + derived.apps)
AREAS["telegram"] = Area((*AREAS["telegram"].paths, "tests/p2_telegram/**"), AREAS["telegram"].apps)

# Ownership that crosses the module/app boundary (retired modules remain capabilities).
EXTRA_APPS = {
    "makerspaces": ("tenancy", "platform"), "admin_api": ("inventory", "lending"),
    "integrations": ("notifications",), "operations": ("inventory", "audit"),
    "machines": ("lending",), "printing": ("machine_service",),
    "maintenance": ("machines", "bookings"), "procurement": ("machines", "bookings"),
    "warranty": ("machines", "bookings"), "card_designs": ("membership",),
    "id_programmes": ("membership",), "maker_formats": ("inventory", "machines"),
    "roadmap": ("platform",),
}
APP_AREAS: dict[str, set[str]] = {}
for app, names in EXTRA_APPS.items():
    for name in names:
        prior = AREAS[name]
        AREAS[name] = Area((*prior.paths, f"tests/{app}/**"), (*prior.apps, app))
for name, area in AREAS.items():
    for app in area.apps:
        APP_AREAS.setdefault(app, set()).add(name)

# Feature directories can differ from backend app and module names.
FRONTEND = {
    "auth": ("auth", "member_accounts"), "staff": ("platform", "staff_admin"),
    "inventory": ("inventory", "public_inventory", "lending"),
    "loanDelight": ("lending",), "kiosk": ("lending", "devices"),
    "members": ("membership", "member_accounts"), "community": ("membership",),
    "profile": ("membership",), "cards": ("membership",), "guestPasses": ("membership",),
    "cardEraser": ("membership",), "walletCredentials": ("membership", "mobile"),
    "accountActivity": ("membership", "payments_ledger"), "accountSavedDetails": ("member_accounts",),
    "finance": ("payments_ledger",), "payments": ("payments", "payments_ledger"),
    "donations": ("payments_ledger",), "bookingDelight": ("bookings",),
    "repairs": ("inventory", "machines", "bookings"), "incidents": ("inventory", "machines"),
    "messaging": ("notifications",), "organizationLeave": ("organizations",),
    "printing": ("machine_service",), "supervised-sessions": ("machines",),
    "spaceDisplay": ("presence",), "stats": ("reports", "analytics"),
}
SHELL_FEATURES = {"discover", "discovery", "docs", "help", "hub", "landing", "legal", "public", "publicPages"}


def owners_for_app(app):
    return set(APP_AREAS.get(app, ()))


def owners_for_feature(feature):
    if feature in SHELL_FEATURES or feature.split(".")[0] in {"AboutPage", "LandingPage", "NotFoundPage"}:
        return {"frontend_shell"}
    if feature.startswith("machine-"):
        return {"machines", "machine_service"}
    if feature.startswith("platform") or feature in {"deployment", "hosting"}:
        return {"platform"}
    return set(FRONTEND.get(feature, (feature,) if feature in AREAS else ()))


@lru_cache(maxsize=None)
def _test_sources(backend):
    return {p for p in (backend / "tests").rglob("*.py")}


@lru_cache(maxsize=None)
def _references(path):
    """Static parsing never imports a test or runs its fixtures."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    modules, strings = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                package = list(path.relative_to(BACKEND).parts[:-1])
                base = ".".join(package[:len(package) - node.level + 1])
                module = ".".join(filter(None, (base, node.module)))
            else:
                module = node.module or ""
            modules.add(module)
            modules.update(f"{module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.add(node.value)
    return modules, strings


@lru_cache(maxsize=None)
def _direct_owners(path):
    relative = path.relative_to(BACKEND).as_posix()
    found = {name for name, area in AREAS.items() if any(fnmatchcase(relative, p) for p in area.paths)}
    modules, strings = _references(path)
    helpers = set()
    for value in strings:
        if value in AREAS:
            found.add(value)
        prefix = value.split(".")[0]
        if prefix in AREAS and "." in value:
            found.add(prefix)
        if value.startswith(("charges.", "billing.", "finance.")):
            found.add("payments_ledger")
        modules.update(re.findall(r"\bapps\.[a-z_]+(?:\.[a-z_]+)*", value))
    for module in modules:
        parts = module.split(".")
        if len(parts) > 1 and parts[0] == "apps":
            found.update(owners_for_app(parts[1]))
        elif parts[0] == "config":
            found.add("platform")
        elif parts[0] == "tests":
            helper = BACKEND.joinpath(*parts).with_suffix(".py")
            if helper in _test_sources(BACKEND) and helper.name != "conftest.py":
                helpers.add(helper)
    return found, helpers


@lru_cache(maxsize=None)
def areas_for_test(path):
    found, pending, visited = set(), [Path(path).resolve()], set()
    while pending:
        current = pending.pop()
        if current not in visited:
            visited.add(current)
            owners, helpers = _direct_owners(current)
            found.update(owners)
            pending.extend(helpers)
    return frozenset(found)


def interconnected(names):
    """Both directions and all depths: a parent change can break its dependents."""
    resolved = set(names)
    unknown = resolved - AREAS.keys()
    if unknown:
        raise ValueError(f"Unknown areas: {', '.join(sorted(unknown))}")
    edges = [(m.key, parent) for m in MODULES for parent in m.requires_modules]
    while True:
        expanded = resolved | {end for a, b in edges if {a, b} & resolved for end in (a, b)}
        if expanded == resolved:
            return resolved
        resolved = expanded


def affected(paths):
    """None means shared/unclassified changes require the full suite; empty means no changes."""
    names = set()
    for path in paths:
        parts = path.replace("\\", "/").split("/")
        if parts[:2] == ["backend", "apps"] and len(parts) > 2:
            owners = owners_for_app(parts[2])
        elif parts[:3] == ["frontend", "src", "features"] and len(parts) > 3:
            owners = owners_for_feature(parts[3])
        elif parts[:2] == ["backend", "tests"] and path.endswith(".py") and (ROOT / path).is_file():
            owners = areas_for_test(ROOT / path)
        else:
            return None
        if not owners or path.endswith("/areas.py") or "/module_registry" in path:
            return None
        names.update(owners)
    return interconnected(names)


def marker_expression(names):
    unknown = set(names) - AREAS.keys()
    if unknown:
        raise ValueError(f"Unknown areas: {', '.join(sorted(unknown))}; use --list")
    return " or ".join(f"area_{name}" for name in sorted(set(names)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--area", action="append", default=[])
    parser.add_argument("--area-affected", metavar="REF")
    args = parser.parse_args(argv)
    try:
        marker_expression(args.area)
        names = set(args.area)
        if args.area_affected is not None:
            if not args.area_affected.strip():
                raise ValueError("--area-affected needs a non-empty ref")
            result = subprocess.run(
                ["git", "diff", "--name-only", "-z", "--end-of-options", args.area_affected, "--"],
                cwd=ROOT, capture_output=True, check=True,
            )
            changed = affected(result.stdout.decode("utf-8").strip("\0").split("\0") if result.stdout else [])
            if changed is None:
                print("ALL")
                return
            names.update(changed)
        print("\n".join(sorted(AREAS)) if args.list else marker_expression(names) or "NONE")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
