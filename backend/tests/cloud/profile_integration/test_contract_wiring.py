"""Local-only, dependency-free checks; may also run directly without Django/pytest."""

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[3]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from cloud_contracts.deployment import DeploymentSelection, parse_selection
from cloud_contracts.jobs import TickResponse
from apps.backup.archive_metadata import settings_manifest
from apps.backup.settings_policy import POLICIES, Policy


def load_helper(name):
    spec = importlib.util.spec_from_file_location(
        f"cloud_test_{name}", BACKEND / "config" / "cloud_settings" / f"{name}.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tasks = load_helper("tasks")
free = load_helper("free")
urls = load_helper("urls")
# Configuration only depends on this static exception type, not Django runtime.
import types
with patch.dict(sys.modules, {"django": types.ModuleType("django"), "django.core": types.ModuleType("django.core"), "django.core.exceptions": types.SimpleNamespace(ImproperlyConfigured=ValueError)}):
    configuration = load_helper("configuration")
    wiring = load_helper("wiring")


class Env:
    def __init__(self, values=None):
        self.values = values or {}
        self.reads = []

    def __call__(self, name, default=None):
        self.reads.append(name)
        return self.values.get(name, default)

    def bool(self, name, default=False):
        return str(self(name, default)).lower() in ("true", "1")

    def list(self, name, default=None):
        return self(name, default or [])

    def json(self, name, default=None):
        return self(name, default or {})

    def int(self, name, default=None):
        value = self(name, default)
        return None if value is None else int(value)


class RemoveHelperImports(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        return ast.copy_location(ast.Pass(), node) if (
            node.module or ""
        ).startswith(("config.cloud_settings", "apps.operations.cloud_jobs.catalog")) else node


def execute_settings_tail(selection, values=None, profile="", scheduler=""):
    """Execute the real wiring with preexisting settings, without importing Django.

    Only helper import statements are substituted; all branches/assignments and
    env reads are the production settings.py code. This is not a DB/runtime test.
    """
    source = (BACKEND / "config/settings.py").read_text(encoding="utf-8")
    start = source.index("# Applied after legacy settings")
    end = source.index("# --- lane L5 (release 2): payer-facing", start)
    tail = source[start:end]
    tree = ast.fix_missing_locations(RemoveHelperImports().visit(ast.parse(tail)))
    env = Env(values)
    state = {
        "env": env, "_deployment": selection,
        "SPACEWORKS_DEPLOYMENT_MODE": selection.mode,
        "CLOUD_TASK_PROFILE": profile, "CLOUD_SCHEDULER": scheduler,
        "CELERY_BROKER_URL": "legacy-broker", "CELERY_TASK_ALWAYS_EAGER": False,
        "CELERY_RESULT_BACKEND": "legacy-result", "LIVE_REDIS_URL": "legacy-live",
        "CELERY_BEAT_SCHEDULE": {"legacy-task": "legacy-schedule"},
        "CACHES": {"default": {"LOCATION": "legacy-cache"}},
        "TOMBSTONED_APPS": (),
        "task_settings": tasks.task_settings, "free_settings": free.free_settings,
        "cache_config": lambda url: {"LOCATION": url or "spaceworks_cache"},
        "cloud_task_modules": lambda **kwargs: ("reviewed.task.module",),
        "ImproperlyConfigured": ValueError,
        "deployment_settings": configuration.deployment_settings,
        "beat_entries": lambda: {},
    }
    exec(compile(tree, "settings-tail", "exec"), state)
    return state, env


class ContractWiringTests(unittest.TestCase):
    def test_provider_helper_matches_real_settings_consumer_and_keeps_fallback(self):
        source = (BACKEND / "config/settings_delivery.py").read_text(encoding="utf-8")
        start = source.index('EMAIL_BACKEND = env(')
        end = source.index('# Async email', start)
        tree = ast.fix_missing_locations(RemoveHelperImports().visit(ast.parse(source[start:end])))
        for provider in ("", "smtp", "resend", "brevo", "postmark", "ses", "mailgun", "sendgrid"):
            state = {"env": Env({"EMAIL_PROVIDER": provider,
                "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
                "EMAIL_PROVIDER_CONFIG_FILE": "/private/mail.json", "EMAIL_PROVIDER_WEBHOOKS_ENABLED": True}),
                "provider_email": wiring.provider_email, "INSTALLED_APPS": []}
            with self.subTest(provider=provider):
                exec(compile(tree, "settings-email", "exec"), state)
                self.assertEqual(state["EMAIL_BACKEND"], "django.core.mail.backends.locmem.EmailBackend")
                self.assertEqual(state["EMAIL_PROVIDER_CONFIG_FILE"], "/private/mail.json")
                self.assertTrue(state["EMAIL_PROVIDER_WEBHOOKS_ENABLED"])
                self.assertEqual(state["INSTALLED_APPS"], [])

    def test_unset_and_explicit_defaults_match(self):
        self.assertEqual(parse_selection({}), DeploymentSelection("host", "full"))
        self.assertEqual(parse_selection({}), parse_selection({
            "SPACEWORKS_DEPLOYMENT_MODE": "host", "SPACEWORKS_DEPLOYMENT_PROFILE": "full",
        }))

    def test_invalid_selectors_refuse(self):
        for key in ("SPACEWORKS_DEPLOYMENT_MODE", "SPACEWORKS_DEPLOYMENT_PROFILE"):
            for value in ("", "unknown", "FULL", " full "):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    parse_selection({key: value})

    def test_free_requires_explicit_managed(self):
        with self.assertRaises(ValueError):
            parse_selection({"SPACEWORKS_DEPLOYMENT_PROFILE": "free"})
        self.assertTrue(parse_selection({
            "SPACEWORKS_DEPLOYMENT_MODE": "managed", "SPACEWORKS_DEPLOYMENT_PROFILE": "free",
        }).is_free)

    def test_host_full_preserves_all_effective_values_and_never_reads_free(self):
        knobs = json.loads((ROOT / "deploy/contracts/environment.json").read_text())["implemented_by_i"]
        state, env = execute_settings_tail(DeploymentSelection(), {
            key: "invalid-free-value" for key in knobs if key.startswith("FREE_")
        })
        self.assertFalse(any(name.startswith("FREE_") for name in env.reads))
        self.assertEqual(state["CELERY_BROKER_URL"], "legacy-broker")
        self.assertFalse(state["CELERY_TASK_ALWAYS_EAGER"])
        self.assertEqual(state["CACHES"]["default"]["LOCATION"], "legacy-cache")
        self.assertEqual(state["CELERY_BEAT_SCHEDULE"], {"legacy-task": "legacy-schedule"})
        self.assertNotIn("CELERY_IMPORTS", state)
        self.assertNotIn("FREE_TICK_SECRET", state)

    def test_full_managed_redis_ignores_malformed_free_caps(self):
        state, env = execute_settings_tail(DeploymentSelection("managed", "full"), {
            "CELERY_BROKER_URL": "rediss://broker.example/0", "FREE_DB_CAP_BYTES": "bad",
            "FREE_TICK_SECRET": "configured-but-inert",
        })
        self.assertFalse(any(name.startswith("FREE_") for name in env.reads))
        self.assertEqual(state["CLOUD_SCHEDULER"], "beat")
        self.assertEqual(state["CELERY_BEAT_SCHEDULE"], {"legacy-task": "legacy-schedule"})

    def test_full_brokerless_preserves_schedule_and_has_no_redis_fallback(self):
        state, _ = execute_settings_tail(DeploymentSelection(), profile="brokerless")
        self.assertEqual(state["CELERY_BROKER_URL"], "")
        self.assertEqual(state["CACHES"]["default"]["LOCATION"], "spaceworks_cache")
        self.assertEqual(state["CELERY_BEAT_SCHEDULE"], {"legacy-task": "legacy-schedule"})

    def test_free_uses_tick_shared_cache_empty_brokers_and_no_beat(self):
        state, _ = execute_settings_tail(DeploymentSelection("managed", "free"))
        self.assertEqual(state["CLOUD_TASK_PROFILE"], "brokerless")
        self.assertEqual(state["CLOUD_SCHEDULER"], "tick")
        self.assertEqual(state["CELERY_BROKER_URL"], "")
        self.assertIsNone(state["CELERY_RESULT_BACKEND"])
        self.assertEqual(state["LIVE_REDIS_URL"], "")
        self.assertEqual(state["CACHES"]["default"]["LOCATION"], "spaceworks_cache")
        self.assertEqual(state["CELERY_BEAT_SCHEDULE"], {})
        self.assertEqual(state["FREE_TICK_BUDGET_SECONDS"], 20)
        self.assertIsNone(state["FREE_DB_CAP_BYTES"])

    def test_free_rejects_conflicting_urls(self):
        for key in ("CELERY_BROKER_URL", "CACHE_URL", "LIVE_REDIS_URL", "CELERY_RESULT_BACKEND"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                tasks.task_settings(Env({key: "rediss://example/0"}), DeploymentSelection("managed", "free"))

    def test_free_storage_proof_covers_cycle_and_one_missed_tick(self):
        for interval in (600, 1800, 3600):
            with self.subTest(interval=interval):
                state, _ = execute_settings_tail(DeploymentSelection("managed", "free"), {
                    "FREE_TICK_INTERVAL_SECONDS": interval,
                })
                self.assertEqual(state["STORAGE_CAPABILITY_TTL_SECONDS"], 3 * interval + 20)
                for short_ttl in (900, 2 * interval, 3 * interval + 19):
                    with self.assertRaises(ValueError):
                        execute_settings_tail(DeploymentSelection("managed", "free"), {
                            "FREE_TICK_INTERVAL_SECONDS": interval,
                            "STORAGE_CAPABILITY_TTL_SECONDS": short_ttl,
                        })

    def test_full_proof_ttl_and_free_knob_isolation_unchanged(self):
        for selection in (DeploymentSelection(), DeploymentSelection("managed", "full")):
            state, env = execute_settings_tail(selection, {
                "FREE_TICK_INTERVAL_SECONDS": "invalid", "FREE_TICK_BUDGET_SECONDS": "invalid",
            })
            self.assertEqual(state["STORAGE_CAPABILITY_TTL_SECONDS"], 900)
            self.assertFalse(any(name.startswith("FREE_") for name in env.reads))

    def test_free_refresh_cycle_cannot_exceed_the_proof_ceiling(self):
        with self.assertRaises(ValueError):
            execute_settings_tail(DeploymentSelection("managed", "free"), {
                "FREE_TICK_INTERVAL_SECONDS": 86400,
            })

    def test_free_rejects_non_eager_or_resident_scheduler_or_redis(self):
        for values, profile, scheduler in (
            ({"CELERY_TASK_ALWAYS_EAGER": "False"}, "", ""),
            ({}, "redis", ""), ({}, "", "beat"), ({}, "", "loop"),
            ({}, "", "external"),
        ):
            with self.subTest(profile=profile, scheduler=scheduler), self.assertRaises(ValueError):
                tasks.task_settings(Env(values), DeploymentSelection("managed", "free"), profile=profile, scheduler=scheduler)

    def test_full_rejects_tick_even_with_secret(self):
        with self.assertRaises(ValueError):
            tasks.task_settings(Env({"FREE_TICK_SECRET": "configured"}), DeploymentSelection(), scheduler="tick")

    def test_free_bounds_refuse_before_effects(self):
        for key, values in {
            "FREE_TICK_BUDGET_SECONDS": (0, 21), "FREE_TICK_INTERVAL_SECONDS": (0, 86401),
            "FREE_TICK_RATE_LIMIT_PER_MINUTE": (0, 61), "FREE_DB_CAP_BYTES": (0, -1),
            "FREE_OBJECT_CAP_BYTES": (0, -1), "FREE_EMAIL_DAILY_CAP": (0, -1),
        }.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    execute_settings_tail(DeploymentSelection("managed", "free"), {key: value})

    def test_full_url_branch_does_not_import_django_or_J(self):
        with patch("builtins.__import__", side_effect=AssertionError("unexpected import")):
            self.assertEqual(urls.free_tick_paths("full"), [])

    def test_wire_fixture_matches_response_type_and_secret_header(self):
        fixture = json.loads((ROOT / "deploy/contracts/free-tick.openapi.json").read_text())
        post = fixture["paths"]["/api/v1/internal/free/tick"]["post"]
        self.assertEqual(set(post["responses"]), {"200", "400", "403", "404", "405", "413", "415", "429", "503"})
        self.assertTrue(post["x-internal"])
        components = fixture["components"]
        self.assertEqual(set(components["schemas"]["TickResponse"]["required"]), set(TickResponse.__annotations__))
        self.assertEqual(components["securitySchemes"]["FreeTickSecret"]["name"], "X-Cron-Secret")

    def test_pending_programmes_cannot_claim_complete(self):
        fixture = json.loads((ROOT / "deploy/contracts/programmes.json").read_text())
        self.assertEqual(fixture["status"], "reviewed_current_tree")
        paths = []
        for name in ("pages", "events", "reimbursement"):
            self.assertEqual(fixture[name]["status"], "not_present_in_current_tree")
            self.assertFalse(fixture[name]["actual_hooks"])
            paths.extend(item["path"] for item in fixture[name]["required_tasks"])
        self.assertEqual(len(paths), len(set(paths)))

    def test_legacy_archive_does_not_require_new_full_or_free_fingerprints(self):
        with patch.dict("os.environ", {}, clear=True):
            archived = settings_manifest()
        names = json.loads((ROOT / "deploy/contracts/environment.json").read_text())["implemented_by_i"]
        for name in names:
            archived.pop(name, None)  # a pre-cloud archive has none of these facts
        tree = ast.parse((BACKEND / "apps/backup/management/commands/backup_preflight.py").read_text())
        check = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "check_setting_policies")
        namespace = {"POLICIES": POLICIES, "Policy": Policy, "os": __import__("os"),
                     "hashlib": hashlib, "CommandError": RuntimeError, "sys": sys}
        exec(compile(ast.Module(body=[check], type_ignores=[]), "preflight-check", "exec"), namespace)
        with patch.dict("os.environ", {
            "SPACEWORKS_DEPLOYMENT_MODE": "host", "SPACEWORKS_DEPLOYMENT_PROFILE": "full",
            "FREE_TICK_SECRET": "set-but-inert", "FREE_DB_CAP_BYTES": "malformed-but-inert",
        }, clear=True):
            namespace["check_setting_policies"](archived)
        self.assertTrue(POLICIES["FREE_TICK_SECRET"].secret_bearing)


if __name__ == "__main__":
    unittest.main()
