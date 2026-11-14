"""CX15: exercise the settings and real website CSP builder without a database or vendor account."""
import copy
import os
from pathlib import Path
import re
import shutil
import subprocess

from django.core.exceptions import ImproperlyConfigured
import pytest

from config.web_analytics import mixpanel_settings


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "frontend/docker-entrypoint.d/40-web-analytics.sh"
TOKEN = "cx15-public-token"
API = "https://collector.example.test"
SDK = "https://sdk.example.test"


def configured(values, policy):
    return mixpanel_settings(lambda key, default="": values.get(key, default), policy)


def test_disabled_settings_do_not_change_any_csp_directive():
    policy = {"DIRECTIVES": {"script-src": ["'self'"], "connect-src": ["'self'", "https://api.example.test"]}}
    before = copy.deepcopy(policy)
    assert configured({"WEB_TELEMETRY_MIXPANEL_API_HOST": API}, policy) == ("", API, "https://cdn.mxpnl.com")
    assert policy == before


def test_enabled_settings_add_only_the_two_configured_origins_once():
    policy = {"DIRECTIVES": {"script-src": ["'self'"]}}
    values = {"WEB_TELEMETRY_MIXPANEL_TOKEN": TOKEN, "WEB_TELEMETRY_MIXPANEL_API_HOST": API,
              "WEB_TELEMETRY_MIXPANEL_SDK_HOST": SDK}
    assert configured(values, policy) == (TOKEN, API, SDK)
    configured(values, policy)
    assert policy == {"DIRECTIVES": {"script-src": ["'self'", SDK], "connect-src": ["'self'", API]}}


@pytest.mark.parametrize("key,value", [
    ("TOKEN", 'public\n");alert(1)//'), ("TOKEN", "public\n"), ("TOKEN", "x" * 129),
    *[(key, value) for key in ("API_HOST", "SDK_HOST") for value in (
        "http://example.test", "https://*.example.test", "https://user:pass@example.test",
        "https://example.test/path", "https://example.test?", "https://example.test#",
        "https://example.test\\evil", "https://example.test\n", 'https://example.test\n");alert(1)//',
    )],
])
def test_unsafe_config_refused_before_mutating_policy(key, value):
    policy = {"DIRECTIVES": {"script-src": ["'self'"]}}
    before = copy.deepcopy(policy)
    with pytest.raises(ImproperlyConfigured):
        configured({"WEB_TELEMETRY_MIXPANEL_TOKEN": TOKEN, f"WEB_TELEMETRY_MIXPANEL_{key}": value}, policy)
    assert policy == before


def website(tmp_path, values):
    env = {**os.environ, **dict.fromkeys((
        "WEB_ANALYTICS_SCRIPT_URL", "WEB_ANALYTICS_COLLECT_URL", "WEB_ANALYTICS_DOMAIN",
        "WEB_ANALYTICS_EXTRA_CONNECT_ORIGINS", "WEB_TELEMETRY_ALLOWED_ORIGINS", "TURNSTILE_SITE_KEY",
        "WEB_TELEMETRY_MIXPANEL_TOKEN", "WEB_TELEMETRY_MIXPANEL_API_HOST", "WEB_TELEMETRY_MIXPANEL_SDK_HOST",
    ), ""), **values, "WEB_ANALYTICS_HEADERS_PATH": str(tmp_path / "headers.conf"),
        "TENANT_CONFIG_PATH": str(tmp_path / "config.js")}
    (tmp_path / "config.js").write_text("", encoding="utf-8")
    result = subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True)
    return result, (tmp_path / "headers.conf").read_text(), (tmp_path / "config.js").read_text()


requires_shell = pytest.mark.skipif(not SCRIPT.exists() or not shutil.which("sh"), reason="frontend tree or sh unavailable")


@requires_shell
def test_disabled_website_has_no_runtime_config_or_csp_change(tmp_path):
    result, baseline, config = website(tmp_path, {})
    assert result.returncode == 0
    assert config == ""
    result, headers, config = website(tmp_path, {"WEB_TELEMETRY_MIXPANEL_API_HOST": API, "WEB_TELEMETRY_MIXPANEL_SDK_HOST": SDK})
    assert result.returncode == 0
    assert headers == baseline
    assert config == ""
    assert "mixpanel" not in headers
    assert "connect-src" not in headers


@requires_shell
def test_website_csp_contains_only_configured_mixpanel_hosts(tmp_path):
    result, baseline, _ = website(tmp_path, {})
    assert result.returncode == 0
    result, headers, config = website(tmp_path, {"WEB_TELEMETRY_MIXPANEL_TOKEN": TOKEN,
        "WEB_TELEMETRY_MIXPANEL_API_HOST": API, "WEB_TELEMETRY_MIXPANEL_SDK_HOST": SDK})
    assert result.returncode == 0, result.stderr
    scripts = re.search(r"script-src ([^;]+)", headers).group(1).split()
    original = re.search(r"script-src ([^;]+)", baseline).group(1).split()
    assert scripts == [*original, SDK]
    connect = re.search(r"connect-src ([^;]+)", headers).group(1).split()
    assert connect == ["'self'", "https://accounts.google.com", "https://oauth2.googleapis.com", "https://appleid.apple.com", API]
    assert config.strip() == (
        f'window.__MIXPANEL__ = new URL("{SDK}").origin === window.location.origin ? undefined : '
        f'{{token: "{TOKEN}", apiHost: "{API}", sdkHost: "{SDK}"}};'
    )
    assert "cdn.mxpnl.com" not in headers
    assert "api.mixpanel.com" not in headers
    assert "*" not in headers


@requires_shell
@pytest.mark.parametrize("key,value", [("TOKEN", 'public\n");alert(1)//'), ("API_HOST", "https://valid.test\nunsafe"),
    ("SDK_HOST", "https://*.example.test"), ("API_HOST", "https://example.test/path")])
def test_website_rejects_injection_and_wildcard_hosts(tmp_path, key, value):
    result, _, config = website(tmp_path, {"WEB_TELEMETRY_MIXPANEL_TOKEN": TOKEN, f"WEB_TELEMETRY_MIXPANEL_{key}": value})
    assert result.returncode == 1
    assert result.stderr.strip() == "Invalid WEB_ANALYTICS configuration"
    assert config == ""


def test_bundled_installs_pass_settings_to_both_backend_and_website():
    for name in ("docker-compose.yml", "docker-compose.prod.yml"):
        text = (ROOT / name).read_text()
        for key in ("TOKEN", "API_HOST", "SDK_HOST"):
            assert text.count(f"      WEB_TELEMETRY_MIXPANEL_{key}:") == 2


def test_public_telemetry_settings_are_explicitly_excluded_from_restore_authority():
    from apps.backup.settings_policy import POLICIES, Policy, SettingPolicy

    for key in ("TOKEN", "API_HOST", "SDK_HOST"):
        assert POLICIES[f"WEB_TELEMETRY_MIXPANEL_{key}"] == SettingPolicy(Policy.EXCLUDED)
