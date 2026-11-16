from pathlib import Path

import pytest
import yaml

KEYS = {"NOTIFICATION_SLACK_REDIRECT_URI", "NOTIFICATION_MATTERMOST_REDIRECT_URI",
        "NOTIFICATION_DISCORD_REDIRECT_URI", "NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS", "WHATSAPP_META_GRAPH_VERSION"}
ROOT = Path(__file__).resolve().parents[3]


def test_new_env_settings_are_declared_and_have_nonblocking_restore_policies(settings):
    from apps.backup.settings_policy import POLICIES, Policy
    assert {key for key in KEYS if hasattr(settings, key)} == KEYS
    for key in KEYS:
        assert POLICIES[key].policy == Policy.VALUE_COMPARISON
        assert not POLICIES[key].blocks_restore


@pytest.mark.parametrize("name", [".env.example", ".env.production.example", "backend/.env.example"])
def test_notification_env_examples_are_complete(name):
    keys = {line.split("=", 1)[0] for line in (ROOT / name).read_text(encoding="utf-8-sig").splitlines()
            if line and not line.startswith("#") and "=" in line}
    assert KEYS <= keys


@pytest.mark.parametrize("name", ["docker-compose.yml", "docker-compose.prod.yml", "docker-compose.cloud.yml"])
def test_new_settings_reach_every_backend_compose_process(name):
    document = yaml.safe_load((ROOT / name).read_text(encoding="utf-8-sig"))
    for service, spec in document["services"].items():
        if service in {"backend", "migrate", "worker", "beat", "live", "cron"}:
            assert KEYS <= set(spec["environment"]), service


@pytest.mark.parametrize("name", ["render.yaml", "deploy/render.managed.yaml"])
def test_render_settings_share_the_new_backend_environment(name):
    document = yaml.safe_load((ROOT / name).read_text(encoding="utf-8-sig"))
    keys = {row["key"] for group in document["envVarGroups"] for row in group["envVars"]}
    assert KEYS <= keys
