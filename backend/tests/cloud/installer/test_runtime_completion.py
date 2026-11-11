"""Local diagnostic contracts and failure behavior. Never contacts a deployed service."""
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]


def load(name):
    alias = name.replace("-", "_").removesuffix(".py")
    spec = importlib.util.spec_from_file_location(alias, ROOT / "scripts/installer" / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMMON = load("probe-common.py")
sys.modules.setdefault("probe_common", COMMON)
SERVICES = load("probe-services.py")
INTEGRATIONS = load("probe-integrations.py")


class RuntimeCompletion(unittest.TestCase):
    def test_scheduler_requires_success_and_heartbeat_not_claim_time(self):
        now = datetime.now(timezone.utc)
        good = {"schema_version": 1, "mode": "beat", "failed": False,
                "heartbeat_at": now, "last_success_at": now.isoformat()}
        self.assertEqual(SERVICES.scheduler(good), "heartbeat_and_success_fresh")
        for changes in ({"last_success_at": None}, {"failed": True}, {"mode": "tick"},
                        {"heartbeat_at": now - timedelta(seconds=181)},
                        {"heartbeat_at": now + timedelta(minutes=1)},
                        {"last_success_at": now.replace(tzinfo=None)}, {"schema_version": 2}):
            with self.subTest(changes=changes), self.assertRaises(COMMON.ProbeError):
                SERVICES.scheduler(dict(good, **changes), now=now)

    def worker_modules(self, eager=False):
        cache = {}
        class Cache:
            get = staticmethod(cache.get)
            delete = staticmethod(lambda key: cache.pop(key, None))
        calls = []
        def send_task(name, *, args, **kwargs):
            calls.append((name, kwargs))
            cache["spaceworks:installer:roundtrip:" + args[0]] = args[0]
        return cache, calls, {
            "config.celery": NS(app=NS(conf=NS(task_always_eager=eager), send_task=send_task)),
            "django.core.cache": NS(cache=Cache()),
            "django.conf": NS(settings=NS(CACHES={"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache"}})),
        }

    def test_worker_submits_a_real_task_and_requires_shared_ack_then_cleans(self):
        cache, calls, modules = self.worker_modules()
        with patch.dict(sys.modules, modules):
            self.assertEqual(SERVICES.worker(), "task_roundtrip_verified")
        self.assertEqual(calls[0][0], "apps.operations.cloud_jobs.diagnostics.installer_roundtrip")
        self.assertFalse(calls[0][1]["retry"])
        self.assertFalse(cache)

    def test_eager_cannot_pass_as_worker_roundtrip(self):
        _, calls, modules = self.worker_modules(eager=True)
        with patch.dict(sys.modules, modules), self.assertRaises(COMMON.ProbeError):
            SERVICES.worker()
        self.assertFalse(calls)

    def test_missing_worker_ack_fails_and_cleans_key(self):
        cache, _, modules = self.worker_modules()
        modules["config.celery"].app.send_task = lambda *a, **k: None
        with patch.dict(sys.modules, modules), patch.object(SERVICES.time, "monotonic", side_effect=[0, 46]):
            with self.assertRaises(COMMON.ProbeError):
                SERVICES.worker()
        self.assertFalse(cache)

    def test_enabled_scanner_requires_fresh_signatures_and_clean_infected_checks(self):
        settings = NS(UPLOAD_SCAN_POLICY="clamav", CLAMD_HOST="fixture.invalid", CLAMD_PORT=3310)
        fresh = "ClamAV 1.4/123/" + datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S %Y")
        with patch.dict(sys.modules, {"django.conf": NS(settings=settings)}):
            with patch.object(INTEGRATIONS, "clamd", side_effect=[fresh, "stream: OK", "stream: Eicar-Test-Signature FOUND"]):
                self.assertEqual(INTEGRATIONS.scanner(), "fresh_signatures_clean_and_infected_verified")
            for responses in (["ClamAV 1.4/123/Mon Jan 01 00:00:00 2001"], [fresh, "stream: ERROR"],
                              [fresh, "stream: OK", "stream: OK"]):
                with patch.object(INTEGRATIONS, "clamd", side_effect=responses), self.assertRaises(COMMON.ProbeError):
                    INTEGRATIONS.scanner()
            with patch.object(INTEGRATIONS, "clamd", side_effect=OSError("private provider error")):
                with self.assertRaises(OSError):
                    INTEGRATIONS.scanner()

    def test_disabled_scanner_is_explicit_not_reachable(self):
        with patch.dict(sys.modules, {"django.conf": NS(settings=NS(UPLOAD_SCAN_POLICY="none"))}):
            self.assertEqual(INTEGRATIONS.scanner(), "explicitly_disabled")

    def test_parent_never_reprints_secret_child_output(self):
        module = load("runtime-probes.py")
        def result(*args, **kwargs):
            name = args[0][-1]
            output = next(iter(module.ALLOWED[name])).encode()
            return NS(returncode=0, stdout=b"secret-key-do-not-log" if name == "worker" else output)
        output = io.StringIO()
        with patch.object(sys, "argv", ["runtime-probes.py"]), patch.object(module.subprocess, "run", side_effect=result), \
             patch.dict(os.environ, {"SPACEWORKS_INSTALLER_REQUIRED_PROBES": ""}), patch("sys.stdout", output), self.assertRaises(SystemExit):
            module.main()
        self.assertNotIn("secret-key-do-not-log", output.getvalue())
        self.assertIn('"worker": "failed"', output.getvalue())

    def test_required_optional_capability_cannot_pass_disabled(self):
        module = load("runtime-probes.py")
        def result(*args, **kwargs):
            name = args[0][-1]
            output = "explicitly_disabled" if name == "scanner" else next(iter(module.ALLOWED[name]))
            return NS(returncode=0, stdout=output.encode())
        with patch.object(sys, "argv", ["runtime-probes.py"]), patch.object(module.subprocess, "run", side_effect=result), \
             patch.dict(os.environ, {"SPACEWORKS_INSTALLER_REQUIRED_PROBES": "scanner"}), patch("sys.stdout", io.StringIO()), \
             self.assertRaises(SystemExit):
            module.main()

    def test_probe_capsule_compiles_without_image_or_host_mount(self):
        code = subprocess.check_output([sys.executable, str(ROOT / "scripts/installer/probe-bundle.py")], timeout=10)
        compile(code, "probe-capsule", "exec")
        self.assertNotIn(b"SECRET_KEY", code)

    def test_edge_requires_verified_https_outside_loopback(self):
        for origin, accepted in (("http://localhost", True), ("http://tools.example.org", False),
                                 ("https://tools.example.org", True), ("https://u:p@tools.example.org", False)):
            with patch.dict(sys.modules, {"django.conf": NS(settings=NS(PUBLIC_APP_BASE_URL=origin))}), \
                 patch.object(INTEGRATIONS, "json_get", return_value={"status": "ready"}):
                if accepted:
                    self.assertIn("verified" if origin.startswith("https:") else "loopback", INTEGRATIONS.edge())
                else:
                    with self.assertRaises(COMMON.ProbeError):
                        INTEGRATIONS.edge()

    def test_unselected_email_never_sends(self):
        modules = {"django.core.mail": NS(EmailMessage=object, get_connection=lambda **kw: self.fail("send")),
                   "django.core.validators": NS(validate_email=lambda value: None),
                   "apps.integrations.email": NS(platform_mail_connection=lambda: self.fail("send"))}
        with patch.dict(sys.modules, modules), patch.dict(os.environ, {"SPACEWORKS_INSTALLER_TEST_EMAIL": ""}):
            self.assertEqual(INTEGRATIONS.email(), "not_selected_configure_and_test_in_control")

    def test_console_email_cannot_count_as_delivery_and_transport_failure_propagates(self):
        for backend, error in (("django.core.mail.backends.console", COMMON.ProbeError),
                               ("django.core.mail.backends.smtp", OSError)):
            class Connection:
                def __enter__(self):
                    raise OSError("private smtp password must not escape child")
                def __exit__(self, *args):
                    pass
            Connection.__module__ = backend
            connection = Connection()
            modules = {"django.core.mail": NS(EmailMessage=object, get_connection=lambda **kw: connection),
                       "django.core.validators": NS(validate_email=lambda value: None),
                       "apps.integrations.email": NS(platform_mail_connection=lambda: (connection, "test@example.invalid"))}
            with patch.dict(sys.modules, modules), patch.dict(os.environ, {"SPACEWORKS_INSTALLER_TEST_EMAIL": "test@example.invalid"}):
                with self.assertRaises(error):
                    INTEGRATIONS.email()

    def test_storage_uses_real_presign_checks_public_and_private_bytes_and_cleans_exact_keys(self):
        storage = load("probe-storage.py")
        deleted, uploaded, requests = [], [], []
        class Body:
            def read(self, count):
                return storage.PAYLOAD
            def close(self):
                pass
        client = NS(get_object=lambda **kwargs: {"Body": Body()},
                    put_object=lambda **kwargs: uploaded.append(kwargs))
        evidence = NS(staging_key=lambda key: "staging/" + key, _client=lambda: client,
                      presigned_upload=lambda *args: {"url": "https://signed.invalid/upload", "method": "PUT", "headers": {}},
                      _public_client=lambda: NS(generate_presigned_url=lambda *args, **kw: "https://private.invalid/key?X-Amz-Secret=test"))
        modules = {"django.conf": NS(settings=NS(AWS_STORAGE_BUCKET_NAME="private", PUBLIC_IMAGE_BUCKET="public",
                                                PUBLIC_IMAGE_BASE_URL="https://images.invalid")),
                   "apps.evidence": NS(storage=evidence),
                   "apps.object_storage": NS(delete_all_versions=lambda *args, **kwargs: deleted.append(kwargs))}
        def request(url, **kwargs):
            requests.append(url)
            if "signed.invalid" in url:
                return 200, b""
            if "private.invalid" in url:
                return 403, b""
            return 200, storage.PAYLOAD
        with patch.dict(sys.modules, modules), patch.object(storage, "request", side_effect=request):
            self.assertEqual(storage.storage(), "private_public_presign_bytes_verified")
        self.assertEqual(len(uploaded), 1)
        self.assertEqual({row["bucket"] for row in deleted}, {"private", "public"})
        self.assertTrue(all(row["key"].startswith(("installer-probes/", "staging/installer-probes/")) for row in deleted))
        self.assertIn("https://private.invalid/key", requests)
        self.assertFalse(any("X-Amz-Secret" in url for url in requests))

    def test_loopback_browser_storage_is_reached_through_the_backend_endpoint_with_its_signed_host(self):
        # A loopback public endpoint is the host's published port; inside the backend
        # network the probe connects to the backend endpoint but keeps the signed Host.
        storage = load("probe-storage.py")
        settings = NS(AWS_S3_PUBLIC_ENDPOINT_URL="http://localhost:9000", AWS_S3_ENDPOINT_URL="http://minio:9000")
        sent = []
        with patch.dict(sys.modules, {"django.conf": NS(settings=settings)}), \
             patch.object(storage, "request", side_effect=lambda url, **kw: sent.append((url, kw)) or (200, b"")):
            storage.browser_request("http://localhost:9000/bucket/key?X-Amz-Signature=s", data=b"x", method="PUT",
                                    headers={"Content-Type": "image/png"})
            storage.browser_request("https://files.example.org/bucket/key")
        self.assertEqual(sent[0], ("http://minio:9000/bucket/key?X-Amz-Signature=s",
                                   {"headers": {"Content-Type": "image/png", "Host": "localhost:9000"},
                                    "data": b"x", "method": "PUT"}))
        self.assertEqual(sent[1], ("https://files.example.org/bucket/key", {"headers": {}}))

    def test_checks_run_with_the_application_on_the_python_path(self):
        # The full image sets no PYTHONPATH and each check runs as a script.
        module = load("runtime-probes.py")
        environments = []
        def result(*args, **kwargs):
            environments.append(kwargs["env"])
            return NS(returncode=0, stdout=next(iter(module.ALLOWED[args[0][-1]])).encode())
        with patch.object(sys, "argv", ["runtime-probes.py"]), patch.object(module.subprocess, "run", side_effect=result), \
             patch.dict(os.environ, {"SPACEWORKS_INSTALLER_REQUIRED_PROBES": ""}), patch("sys.stdout", io.StringIO()):
            module.main()
        self.assertEqual(len(environments), len(module.ALLOWED))
        self.assertTrue(all(env["PYTHONPATH"].split(os.pathsep)[0] == os.getcwd() for env in environments))

    def test_live_health_uses_an_allowed_backend_host(self):
        hosts = []
        transport = NS(redis_client=lambda: None, live_redis_url=lambda: "")
        with patch.object(SERVICES, "json_get", side_effect=lambda url, host=None: hosts.append((url, host)) or {}), \
             patch.dict(sys.modules, {"apps.operations": NS(live=transport)}):
            self.assertEqual(SERVICES.live(), "poll_fallback_readiness_verified")
        self.assertEqual(hosts[0], ("http://live:8000/api/v1/health/", "backend"))

    def test_storage_failure_still_attempts_both_exact_cleanups(self):
        storage = load("probe-storage.py")
        deleted = []
        evidence = NS(staging_key=lambda key: "staging/" + key, _client=lambda: object(),
                      presigned_upload=lambda *args: {"url": "https://fixture.invalid", "method": "PUT", "headers": {}})
        modules = {"django.conf": NS(settings=NS(AWS_STORAGE_BUCKET_NAME="private", PUBLIC_IMAGE_BUCKET="public")),
                   "apps.evidence": NS(storage=evidence),
                   "apps.object_storage": NS(delete_all_versions=lambda *args, **kwargs: deleted.append(kwargs))}
        with patch.dict(sys.modules, modules), patch.object(storage, "request", side_effect=OSError("down")):
            with self.assertRaises(OSError):
                storage.storage()
        self.assertEqual(len(deleted), 2)


if __name__ == "__main__":
    unittest.main()
