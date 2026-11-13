"""SECFIX-B: the SPA always gets a script CSP baseline, and the shell needs no inline script for it.

Runs the real frontend entrypoint (frontend/docker-entrypoint.d/40-web-analytics.sh). No database.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "frontend" / "docker-entrypoint.d" / "40-web-analytics.sh"
pytestmark = pytest.mark.skipif(not SCRIPT.exists() or not shutil.which("sh"), reason="frontend tree or sh unavailable")


def headers(tmp_path, **settings):
    env = {**os.environ, "WEB_ANALYTICS_SCRIPT_URL": "", "WEB_ANALYTICS_COLLECT_URL": "", "WEB_ANALYTICS_DOMAIN": "",
           "WEB_TELEMETRY_ALLOWED_ORIGINS": "", "TURNSTILE_SITE_KEY": "", **settings,
           "WEB_ANALYTICS_HEADERS_PATH": str(tmp_path / "h.conf"), "TENANT_CONFIG_PATH": str(tmp_path / "c.js")}
    subprocess.run(["sh", str(SCRIPT)], env=env, check=True)
    return (tmp_path / "h.conf").read_text()


def test_disabled_analytics_still_emits_a_script_baseline(tmp_path):
    text = headers(tmp_path)
    assert "frame-ancestors 'none'" in text
    policy = re.search(r'Content-Security-Policy "(script-src[^"]+)"', text).group(1)
    assert policy.startswith("script-src 'self' 'wasm-unsafe-eval' ")
    assert "object-src 'none'" in policy and "base-uri 'self'" in policy
    # No connect-src here: API and object-storage origins are only declared by the opt-in policy.
    assert "connect-src" not in policy


@pytest.mark.parametrize("env_settings", [{}, {"TURNSTILE_SITE_KEY": "0x4AAAAAAA"}, {
    "WEB_ANALYTICS_SCRIPT_URL": "https://plausible.example/js/script.manual.js",
    "WEB_ANALYTICS_COLLECT_URL": "https://plausible.example/api/event", "WEB_ANALYTICS_DOMAIN": "app.example"}])
def test_no_mode_allows_inline_or_eval_script(tmp_path, env_settings):
    # Not named `settings`: that is pytest-django's fixture and the autouse conftest would receive this dict.
    text = headers(tmp_path, **env_settings)
    assert "'unsafe-inline'" not in text and "'unsafe-eval'" not in text
    assert "object-src 'none'; base-uri 'self'" in text


def test_turnstile_origin_is_allowed_only_when_configured_even_without_analytics(tmp_path):
    assert "challenges.cloudflare.com" not in headers(tmp_path)
    assert "challenges.cloudflare.com" in headers(tmp_path, TURNSTILE_SITE_KEY="0x4AAAAAAA")


def test_shell_has_no_inline_script_and_boot_script_is_served():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for tag in re.findall(r"<script\b[^>]*>", html):
        assert " src=" in tag, f"inline script blocked by the CSP: {tag}"
    assert (ROOT / "frontend" / "public" / "boot.js").exists()
    nginx = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    block = nginx.split("location = /boot.js {", 1)[1].split("}", 1)[0]
    assert "include /etc/nginx/analytics-headers.conf;" in block
