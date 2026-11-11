"""Local recipe contract checks. Provider schemas/live acceptance are separate."""

from datetime import date
import base64
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from cloud_setup.environment import effective_environment
from cloud_setup.recipes import render_blueprint
from cloud_setup.native import cloud_run, render_provider


def answers(free=False, provider="render"):
    path = ROOT / "deploy/cloud" / ("free.answers.example.json" if free else "answers.example.json")
    result = json.loads(path.read_text())
    result.update(provider=provider, backend_image="ghcr.io/spaceworks-labs/spaceworks-backend@sha256:" + "a" * 64)
    if free:
        result["free"]["checked_on"] = date.today().isoformat()
    return result


def blueprint(path):
    # Render artifacts use one YAML-1.2 JSON flow object per list entry. This
    # checks the actual source contract without claiming full YAML/schema lint.
    services, variables = [], []
    in_services = False
    for line in path.read_text().splitlines():
        if line == "services:":
            in_services = True
        if line.lstrip().startswith("- {"):
            value = json.loads(line.strip()[2:])
            (services if in_services else variables).append(value)
    return services, variables


class RecipeTests(unittest.TestCase):
    def test_rendered_build_uses_the_one_real_release_target_for_every_runtime_profile(self):
        import re
        from cloud_setup.render import render

        dockerfile = (ROOT / "backend/Dockerfile").read_text()
        targets = set(re.findall(r"^FROM\s+.+?\s+AS\s+(\S+)", dockerfile, re.MULTILINE | re.IGNORECASE))
        for free, task_profile, roles in ((False, "redis", ["web", "worker", "beat"]),
                                          (False, "brokerless", ["web", "worker", "scheduler"]),
                                          (True, "brokerless", ["web"])):
            with self.subTest(free=free, task_profile=task_profile):
                a = answers(free)
                a["task_profile"] = task_profile
                values = effective_environment(a, {"FREE_TICK_SECRET": "synthetic-local-test-key"} if free else {})
                captured = {}
                with patch("cloud_setup.render.write_private", side_effect=lambda path, text: captured.update({Path(path).name: text})), \
                        patch("cloud_setup.render.write_json"), patch("cloud_setup.recipes.render_native"):
                    render(Path("/private"), values, a)
                deployment = json.loads(captured["deployment.json"])
                self.assertIn(deployment["image_build"]["target"], targets)
                self.assertEqual(deployment["image_build"]["target"], "release")
                self.assertEqual(deployment["image_build"]["context"], "backend")
                self.assertEqual(deployment["image_build"]["named_context"], "cloud_tooling=.")
                self.assertEqual(deployment["image_variant"], "full")
                self.assertEqual(deployment["backend_image"], a["backend_image"])
                self.assertEqual(deployment["deployment_mode"], "managed")
                self.assertEqual(deployment["profile"], "free" if free else "full")
                self.assertEqual([role["name"] for role in deployment["roles"]], roles)
                runtime = json.loads(captured["runtime.environment.json"])
                self.assertEqual(runtime["SPACEWORKS_DEPLOYMENT_PROFILE"], deployment["profile"])
                self.assertEqual(runtime["CLOUD_TASK_PROFILE"], task_profile)
                self.assertEqual(deployment["release"]["argv"],
                                 ["--role", "migrate", "python", "-m", "scripts.run_cloud_role", "release"])

    def test_rendered_edge_secrets_are_separate_from_runtime_and_maintenance(self):
        from cloud_setup.render import render
        a = answers()
        values = effective_environment(a, {"TRUSTED_EDGE_INGRESS_SECRET": "edge-only-protected-value-1234567890",
            "DATABASE_URL": "runtime-sentinel", "DATABASE_MAINTENANCE_URL": "owner-sentinel",
            "SPACEWORKS_MAINTENANCE_DATABASE_URL": "legacy-owner-sentinel", "AWS_SECRET_ACCESS_KEY": "storage-sentinel"})
        captured = {}
        with patch("cloud_setup.render.write_private", side_effect=lambda path, text: captured.update({Path(path).name: text})), \
                patch("cloud_setup.render.write_json"), patch("cloud_setup.recipes.render_native"):
            render(Path("/private"), values, a)
        edge = json.loads(captured["edge.environment.json"])
        self.assertEqual(edge["TRUSTED_EDGE_INGRESS_SECRET"], values["TRUSTED_EDGE_INGRESS_SECRET"])
        self.assertEqual(edge["PUBLIC_ORIGIN"], a["public_origin"])
        self.assertNotIn("sentinel", json.dumps(edge))
        self.assertNotIn("owner-sentinel", captured["runtime.environment.json"])

    def test_render_topologies_and_profile_defaults(self):
        for name, count, scheduler in (("render.yaml", 3, "beat"), ("deploy/render.managed.yaml", 3, "beat"), ("deploy/render.brokerless.yaml", 3, "loop"), ("deploy/render.free.yaml", 1, "tick")):
            services, variables = blueprint(ROOT / name)
            self.assertEqual(len(services), count)
            env = {item["key"]: item.get("value") for item in variables}
            self.assertEqual(env["SPACEWORKS_DEPLOYMENT_MODE"], "managed")
            self.assertEqual(env["CLOUD_SCHEDULER"], scheduler)
            self.assertNotIn("DATABASE_MAINTENANCE_URL", env)
            self.assertIn("PUBLIC_IMAGE_BUCKET", env)
            self.assertIn("EVENT_REIMBURSEMENT_FILE_MAX_BYTES", env)
            for service in services:
                self.assertIn("--role ", service["dockerCommand"])
                self.assertNotIn("startCommand", service)
                self.assertNotIn("entrypoint", service)
                self.assertEqual(service["runtime"], "image")
            if scheduler == "tick":
                self.assertEqual(services[0]["plan"], "free")
                self.assertNotIn("preDeployCommand", services[0])
                self.assertEqual(env["GUNICORN_WORKERS"], "1")
            else:
                self.assertFalse(any(key.startswith("FREE_") for key in env))

    def test_generated_render_secrets_are_prompts_not_literals(self):
        a = answers()
        values = effective_environment(a, {"DATABASE_URL": "sentinel", "PII_MASTER_KEY": "sentinel-key", "DATABASE_MAINTENANCE_URL": "owner-sentinel"})
        rendered = render_blueprint(values, a)
        self.assertNotIn("sentinel", json.dumps(rendered))
        self.assertNotIn("DATABASE_MAINTENANCE_URL", json.dumps(rendered))

    def test_redis_urls_are_private_and_free_empty_urls_stay_empty(self):
        a = answers()
        secret = "rediss://user:sentinel@cache.example:6380/0"
        rendered = render_blueprint(effective_environment(a, {"CELERY_BROKER_URL": secret}), a)
        self.assertNotIn("sentinel", json.dumps(rendered))
        a = answers(True, "cloud-run")
        a["storage_capabilities_file"] = "/secrets/storage/config.json"
        a["environment"]["EMAIL_PROVIDER_CONFIG_FILE"] = "/secrets/email/config.json"
        values = effective_environment(a, {})
        template = json.loads((ROOT / "deploy/cloud-run/free/web.yaml").read_text())
        result = cloud_run(template, values, a)
        env = {item["name"]: item for item in result["spec"]["template"]["spec"]["containers"][0]["env"]}
        for name in ("CELERY_BROKER_URL", "CACHE_URL", "LIVE_REDIS_URL"):
            self.assertEqual(env[name]["value"], "")

    def test_neon_free_trigger_uses_selected_secret_and_cadence(self):
        a = answers(True, "cloud-run")
        a["database_provider"] = "neon"
        a["free"]["tick_interval_seconds"] = 1800
        values = effective_environment(a, {"FREE_TICK_SECRET": "secret-sentinel"})
        template = json.loads((ROOT / "deploy/cloud-run/free/scheduler.yaml").read_text())
        result = cloud_run(template, values, a)
        self.assertEqual(result["schedule"], "*/30 * * * *")
        self.assertEqual(result["httpTarget"]["headers"]["X-Cron-Secret"], "secret-sentinel")

    def test_brokerless_work_job_has_own_recurring_trigger(self):
        result = json.loads((ROOT / "deploy/cloud-run/work-scheduler.yaml").read_text())
        self.assertEqual(result["schedule"], "* * * * *")
        self.assertTrue(result["httpTarget"]["uri"].endswith("/spaceworks-work-job:run"))

    def test_missing_provider_file_delivery_is_refused(self):
        a = answers(provider="digitalocean")
        values = effective_environment(a, {})
        from cloud_setup.errors import SetupError
        with self.assertRaises(SetupError):
            render_provider(Path("/private"), ROOT / "deploy", values, a)

    def test_fly_has_exact_native_secret_file_sources(self):
        a = answers(provider="fly")
        captured = {}
        with patch("cloud_setup.native.write_private", side_effect=lambda path, text: captured.update({Path(path).name: text})):
            render_provider(Path("/private"), ROOT / "deploy", effective_environment(a, {}), a)
        for text in captured.values():
            value = tomllib.loads(text)
            self.assertEqual(len(value["files"]), 2)
            self.assertTrue(all("secret_name" in item for item in value["files"]))

    def test_cloud_run_free_is_single_web_and_finite_release(self):
        web = json.loads((ROOT / "deploy/cloud-run/free/web.yaml").read_text())
        spec = web["spec"]["template"]["spec"]
        self.assertEqual(spec["containerConcurrency"], 1)
        self.assertEqual(len(spec["containers"]), 1)
        annotations = web["spec"]["template"]["metadata"]["annotations"]
        self.assertEqual(annotations["autoscaling.knative.dev/minScale"], "0")
        self.assertEqual(annotations["autoscaling.knative.dev/maxScale"], "1")
        release = json.loads((ROOT / "deploy/cloud-run/free/release-job.yaml").read_text())
        self.assertEqual(release["kind"], "Job")
        text = json.dumps(web)
        self.assertNotIn("DATABASE_MAINTENANCE_URL", text)
        self.assertNotIn('"command"', text)

    def test_every_native_consumer_receives_effective_settings(self):
        for provider in ("cloud-run", "digitalocean", "koyeb", "fly"):
            a = answers(provider=provider)
            a["task_profile"] = "brokerless"
            a["storage_capabilities_file"] = "/tmp/spaceworks-secrets/storage.json"
            a["environment"]["EMAIL_PROVIDER_CONFIG_FILE"] = "/tmp/spaceworks-secrets/email.json"
            inline = base64.b64encode(b'{}').decode()
            values = effective_environment(a, {"DATABASE_URL": "sentinel", "DATABASE_MAINTENANCE_URL": "owner-sentinel", "SPACEWORKS_EMAIL_PROVIDER_CONFIG_B64": inline, "SPACEWORKS_STORAGE_CAPABILITIES_B64": inline})
            captured = {}
            def save(path, text):
                captured[Path(path).name] = text
            with patch("cloud_setup.native.write_private", side_effect=save):
                render_provider(Path("/private"), ROOT / "deploy", values, a)
            self.assertTrue(captured, provider)
            self.assertTrue(any("EVENT_REIMBURSEMENT_FILE_MAX_BYTES" in text for text in captured.values()), provider)
            for name, text in captured.items():
                if "release" not in name and name not in {"app.yaml"}:
                    self.assertNotIn("owner-sentinel", text)

    def test_fly_nonweb_configs_have_no_autostop_listener(self):
        for role in ("worker", "scheduler"):
            config = tomllib.loads((ROOT / f"deploy/fly/fly.{role}.toml").read_text())
            self.assertNotIn("http_service", config)
            self.assertIn("--role", config["processes"]["app"])

    def test_railway_has_no_fabricated_registered_template(self):
        value = json.loads((ROOT / "deploy/railway/template.json").read_text())
        self.assertIsNone(value["registered_template_url"])
        self.assertIn("draft", value["status"])

    def test_oracle_stays_host_full_northflank_unverified(self):
        oracle = json.loads((ROOT / "deploy/cloud/oracle-always-free.json").read_text())
        self.assertEqual((oracle["deployment_mode"], oracle["deployment_profile"]), ("host", "full"))
        northflank = json.loads((ROOT / "deploy/cloud/northflank-sandbox.json").read_text())
        self.assertEqual(northflank["status"], "verify on signup")
        self.assertFalse(northflank["certified_one_click"])

    @unittest.skipUnless(shutil.which("helm"), "Helm unavailable locally; required integrator rerun")
    def test_managed_helm_brokerless_without_host_pvc(self):
        result = subprocess.run(["helm", "template", "test", str(ROOT / "charts/spaceworks"), "--set", "deploymentMode=managed,taskProfile=brokerless,scheduler=loop,beat.enabled=false,frontend.enabled=false,runtimeSecret=runtime,releaseSecret=release,rolloutGeneration=1,backendDigest=sha256:" + "a" * 64], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("host-gate", result.stdout)
        self.assertIn("name: test-spaceworks-scheduler", result.stdout)

    @unittest.skipUnless(shutil.which("helm"), "Helm unavailable locally; required compatibility rerun")
    def test_existing_host_values_keep_authority_and_commands(self):
        value = "runtimeSecret=runtime,databasePointerSecret=runtime-pointer,migrationPointerSecret=owner-pointer,hostGate.existingClaim=host-gate,beat.existingClaim=beat,rolloutGeneration=1,imageTag=legacy-release,replicas=2"
        result = subprocess.run(["helm", "template", "legacy", str(ROOT / "charts/spaceworks"), "--set", value], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("name: legacy-spaceworks-migrate", result.stdout)
        self.assertIn("host-gate", result.stdout)
        self.assertIn("python, manage.py, migrate, --noinput", result.stdout)
        self.assertIn("spaceworks-backend:legacy-release", result.stdout)
        self.assertNotIn("spaceworks-release", result.stdout)


if __name__ == "__main__":
    unittest.main()
