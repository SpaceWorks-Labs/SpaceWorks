"""Production overlays are tested as layers, not mistaken for standalone manifests."""

import re
from pathlib import Path

import pytest
import yaml

from apps.backup.settings_policy import ENV_SURFACE
from tests.test_env_surface_drift import (
    BACKEND_SERVICES, FRONTEND_KEYS, INFRASTRUCTURE_KEYS, ON_BOX_EXEMPT,
    ON_BOX, _env_calls, _consumer_on_box_fallbacks,
)

ROOT = Path(__file__).resolve().parents[2]
PROGRAMME_DEFAULTS = {
    "ACCOUNT_SAVED_DETAILS_ENABLED": "False", "ACCOUNT_PII_KEY_BROKER": "local",
    "ACCOUNT_PII_MASTER_KEY": "", "ACCOUNT_PII_MASTER_KEY_PREVIOUS": "",
    "ACCOUNT_PII_AWS_KMS_KEY_ID": "", "ACCOUNT_SAVED_ASSET_BUDGET_BYTES": "52428800",
    "ACCOUNT_SAVED_RESUME_SCAN_REQUIRED": "False", "ACCOUNT_SAVED_RESUME_SCANNER": "",
    "EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY": "",
    "EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION": "1", "EVENT_REGISTRATION_CREDENTIAL_KEYS": "{}",
}


class ComposeLoader(yaml.SafeLoader):
    pass


ComposeLoader.add_constructor("!reset", lambda loader, node: loader.construct_sequence(node)
                              if isinstance(node, yaml.SequenceNode) else None)  # `!reset null` is a scalar


@pytest.mark.parametrize("manifest", ["docker-compose.yml", "docker-compose.prod.yml", "docker-compose.cloud.yml"])
def test_programme_environment_reaches_every_application_process_without_new_secrets(manifest):
    document = yaml.load((ROOT / manifest).read_text(encoding="utf-8"), Loader=ComposeLoader)
    for service in BACKEND_SERVICES:
        if service not in document["services"]:
            continue
        environment = document["services"][service].get("environment", {})
        for name, default in PROGRAMME_DEFAULTS.items():
            assert environment[name] == "${" + name + ":-" + default + "}", (manifest, service, name)


@pytest.mark.parametrize("example", [".env.example", ".env.production.example", "backend/.env.example"])
def test_programme_examples_keep_account_and_credential_keys_operator_owned(example):
    source = (ROOT / example).read_text(encoding="utf-8")
    assignments = dict(re.findall(r"^([A-Z][A-Z0-9_]*)=(.*)$", source, re.M))
    for name, default in PROGRAMME_DEFAULTS.items():
        assert assignments[name] == default
    assert "never regenerate" in source


@pytest.mark.parametrize("overlay", ["saas", "tls"])
def test_effective_overlay_environment_keeps_the_complete_production_posture(overlay):
    base = yaml.load((ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"), Loader=ComposeLoader)
    layer = yaml.load((ROOT / f"docker/compose.{overlay}.yml").read_text(encoding="utf-8"), Loader=ComposeLoader)
    known = set(ENV_SURFACE) | FRONTEND_KEYS | INFRASTRUCTURE_KEYS
    required = {
        name for name, default in _env_calls()
        if default and ON_BOX.search(default) and name not in ON_BOX_EXEMPT
    } | set(_consumer_on_box_fallbacks()) | {"TRUSTED_PROXY_COUNT", "TRUST_X_FORWARDED_PROTO"}
    for service in BACKEND_SERVICES:
        if service not in base["services"]:
            continue
        environment = {
            **base["services"][service].get("environment", {}),
            **layer["services"].get(service, {}).get("environment", {}),
        }
        assert required <= environment.keys(), (overlay, service, required - environment.keys())
        assert set(environment) <= known, (overlay, service, set(environment) - known)
    if overlay == "saas":
        expected = layer["services"]["backend"]["environment"]["PLATFORM_DOMAIN_SUFFIX"]
        for service in ("migrate", "worker", "beat"):
            assert layer["services"][service]["environment"]["PLATFORM_DOMAIN_SUFFIX"] == expected


@pytest.mark.parametrize("example", [".env.example", ".env.production.example", "backend/.env.example"])
def test_env_examples_expose_observability_and_reference_the_complete_surface(example):
    source = (ROOT / example).read_text(encoding="utf-8")
    for name in ("METRICS_TOKEN", "SENTRY_DSN", "SENTRY_TRACES_SAMPLE_RATE", "SENTRY_ENVIRONMENT"):
        assert re.search(rf"^\s*(?:#\s*)?{name}=", source, re.M), (example, name)
    assert "docs/environment-reference.md" in source


def test_removed_single_box_shape_is_refused_instead_of_reading_a_deleted_manifest():
    import os
    import shutil
    import subprocess
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("requires bash")
    result = subprocess.run([bash, "-c", 'source "$HELPER"; refuse_single_box_layer single'],
                            env={**os.environ, "HELPER": (ROOT / "scripts/compose-deployment.sh").as_posix()},
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 64
    assert "single-box install shape" in result.stderr and "CURRENTLY INSTALLED" in result.stderr
    assert not (ROOT / "docker/compose.single.yml").exists()
