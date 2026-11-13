"""Deployment contracts; strict YAML parsing permits explicit YAML merge overrides."""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


class StrictComposeLoader(yaml.SafeLoader):
    def compose_mapping_node(self, anchor):
        node = super().compose_mapping_node(anchor)
        # Check the original mapping before SafeLoader expands << merge keys.
        # An inherited key may be overridden; a repeated literal key is an error.
        seen = set()
        for key, _ in node.value:
            if not isinstance(key, yaml.ScalarNode):
                raise yaml.constructor.ConstructorError(
                    None, None, "Compose mapping keys must be scalars", key.start_mark,
                )
            if key.value in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate key: {key.value}", key.start_mark,
                )
            seen.add(key.value)
        return node


def _compose_tag(loader, node):
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return loader.construct_scalar(node)


for tag in ("!reset", "!override"):
    StrictComposeLoader.add_constructor(tag, _compose_tag)


def load(name):
    return yaml.load((ROOT / name).read_text(encoding="utf-8"), Loader=StrictComposeLoader)


COMPOSE_FILES = sorted({
    *ROOT.glob("docker-compose*.yml"), *ROOT.glob("docker-compose*.yaml"),
    *ROOT.glob("docker/**/compose*.yml"), *ROOT.glob("docker/**/compose*.yaml"),
})


@pytest.mark.parametrize("path", COMPOSE_FILES, ids=lambda path: str(path.relative_to(ROOT)))
def test_every_compose_file_has_unique_mapping_keys(path):
    load(path.relative_to(ROOT))


@pytest.mark.parametrize("source", [
    "services: {}\nservices: {}\n",
    "services:\n  frontend:\n    environment: {}\n    environment: {}\n",
    "x-env: &env {METRICS_TOKEN: first, METRICS_TOKEN: second}\n",
])
def test_strict_loader_rejects_duplicates_at_every_depth(source):
    with pytest.raises(yaml.constructor.ConstructorError, match="duplicate key"):
        yaml.load(source, Loader=StrictComposeLoader)


def test_strict_loader_allows_merge_overrides_and_compose_tags():
    document = yaml.load(
        "x-env: &env {DEBUG: 'False'}\n"
        "services: {backend: {environment: {<<: *env, DEBUG: 'True'}, ports: !reset []}}\n",
        Loader=StrictComposeLoader,
    )
    assert document["services"]["backend"]["environment"]["DEBUG"] == "True"


@pytest.mark.parametrize("manifest", ["docker-compose.yml", "docker-compose.prod.yml", "docker-compose.cloud.yml"])
def test_shared_application_environment_passes_station_identity_and_edition(manifest):
    services = load(manifest)["services"]
    for name in ("backend", "live", "migrate", "worker", "beat", "cron", "candidate-backend"):
        if name not in services:
            continue
        environment = services[name]["environment"]
        assert environment["EVENT_STATION_PIN_PEPPER"] == "${EVENT_STATION_PIN_PEPPER:-}", name
        assert environment["SPACEWORKS_EDITION"] == "${SPACEWORKS_EDITION:-makerspace}", name
        if manifest != "docker-compose.yml":
            assert environment["AUTH_COOKIE_SECURE"] == "${AUTH_COOKIE_SECURE:-True}", name
            assert environment["AUTH_COOKIE_SAMESITE"] == "${AUTH_COOKIE_SAMESITE:-None}", name


def test_cloud_live_is_a_fenced_writer_using_the_publishers_bus():
    document = load("docker-compose.cloud.yml")
    services = document["services"]
    assert set(document["x-spaceworks-host-orchestration"]["writer_services"]) == {"backend", "live", "cron"}
    live = services["live"]
    bus = live["environment"]["LIVE_REDIS_URL"]
    assert bus.startswith("${LIVE_REDIS_URL:?")
    for name in ("backend", "cron"):
        assert services[name]["environment"]["LIVE_REDIS_URL"] == bus
    assert live["environment"]["CELERY_BROKER_URL"] == ""
    assert live["restart"] == "unless-stopped"
    assert live["logging"]["options"] == {"max-size": "10m", "max-file": "3"}
    assert live["depends_on"]["orchestration-ready"]["condition"] == "service_completed_successfully"
    assert any(volume.endswith("/public:/run/spaceworks-host:ro") for volume in live["volumes"])
    command = live["command"]
    assert command[:2] == ["--role", "backend"]
    assert command[command.index("-k") + 1] == "gthread"
    assert command[command.index("--timeout") + 1] == "0"
    assert not any(argument.startswith("--max-requests") for argument in command)
    assert services["frontend"]["depends_on"]["live"]["condition"] == "service_started"


def test_tls_edge_restarts_and_bounds_logs():
    edge = load("docker/compose.tls.yml")["services"]["caddy"]
    assert edge["restart"] == "unless-stopped"
    assert edge["logging"] == {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}}


def test_frontend_environment_keeps_analytics_and_control_plane_settings():
    environment = load("docker-compose.prod.yml")["services"]["frontend"]["environment"]
    assert {"WEB_ANALYTICS_SCRIPT_URL", "WEB_ANALYTICS_COLLECT_URL", "WEB_ANALYTICS_DOMAIN",
            "WEB_ANALYTICS_EXTRA_CONNECT_ORIGINS", "CONTROL_PLANE_PROXY",
            "CONTROL_PLANE_ALLOW_CIDRS"} <= environment.keys()


def test_api_edge_special_prefixes_cannot_be_overridden_by_general_regex():
    source = (ROOT / "deploy/nginx.api-only.conf").read_text(encoding="utf-8")
    assert "location ^~ /api/v1/internal/ { return 403; }" in source
    start = source.index("location ^~ /api/v1/live/ {")
    live = source[start:source.index("\n    }", start)]
    for directive in ("proxy_pass http://live:8000;", "proxy_buffering off;",
                      "proxy_read_timeout 3600s;", "proxy_http_version 1.1;"):
        assert directive in live


def test_settings_tools_no_longer_select_retired_deployment_layers():
    for name in ("apply-settings.sh", "control-plane-settings.sh"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "none|tls)" in source
        assert "|single)" not in source
        assert "MAKERSPACE_ALLINONE_IMAGE" not in source


def test_django_embed_response_owns_exact_origin_framing_and_private_referrers():
    from apps.makerspaces.website_serving import PublicCard, embed_response

    card = PublicCard(
        title="Workshop", description="", url="https://space.example.org/event",
        image_url=None, date="", location="", availability="", audience_label="", revision="1",
    )
    response = embed_response(card, ["https://host.example.org"])
    assert response.xframe_options_exempt is True
    assert response["Content-Security-Policy"].endswith("frame-ancestors https://host.example.org")
    assert response["Referrer-Policy"] == "no-referrer"
    assert response["Cache-Control"] == "no-store"
    assert "X-Frame-Options" not in response
