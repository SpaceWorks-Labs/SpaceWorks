"""Dev runserver collects and scrapes without a Gunicorn-created directory."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest
import yaml

RESET = object()


class ComposeLoader(yaml.SafeLoader):
    pass


ComposeLoader.add_constructor("!reset", lambda loader, node: RESET)
ComposeLoader.add_constructor("!override", lambda loader, node: loader.construct_sequence(node))


def compose(filename):
    root = Path(__file__).resolve().parents[3]
    return yaml.load((root / filename).read_text(encoding="utf-8"), Loader=ComposeLoader)


@pytest.mark.parametrize("service", ["backend", "candidate-backend"])
def test_dev_runserver_removes_inherited_multiprocess_storage(service):
    base = compose("docker-compose.yml")["services"][service]
    dev = compose("docker-compose.dev.yml")["services"][service]
    assert "runserver" in dev["command"]
    assert base["environment"]["PROMETHEUS_MULTIPROC_DIR"]
    assert dev["environment"]["PROMETHEUS_MULTIPROC_DIR"] is RESET
    # Match Compose's !reset removal before importing prometheus_client in a fresh
    # interpreter. A blank environment value would still select file-backed metrics.
    environment = dict(os.environ)
    environment.pop("PROMETHEUS_MULTIPROC_DIR", None)
    environment.pop("prometheus_multiproc_dir", None)
    code = textwrap.dedent("""\
        from types import SimpleNamespace
        from django.conf import settings
        settings.configure(ROUTE_METRICS_ENABLED=True, PROMETHEUS_MULTIPROC_DIR="",
                           METRICS_TOKEN="dev-scrape-token")
        from django.http import HttpResponse
        from apps.operations import route_metrics, views_metrics
        from prometheus_client import values
        assert not values.ValueClass._multiprocess
        request = SimpleNamespace(method="GET", resolver_match=SimpleNamespace(
            route="dev-startup/<int:pk>"))
        response = route_metrics.RouteMetricsMiddleware(lambda _: HttpResponse(status=503))(request)
        assert response.status_code == 503
        views_metrics._collect = lambda: ""
        scrape = views_metrics.MetricsView().get(SimpleNamespace(
            headers={"Authorization": "Bearer dev-scrape-token"}))
        assert scrape.status_code == 200
        assert scrape["Cache-Control"] == "private, no-store"
        body = scrape.content.decode()
        assert 'spaceworks_http_requests_total{method="GET",route="dev-startup/<int:pk>",status="503"} 1.0' in body
        assert "spaceworks_http_request_duration_seconds_bucket" in body
        assert "dev-scrape-token" not in body
        print("single-process collection and authenticated scrape passed")
    """)
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[2],
                            env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "authenticated scrape passed" in result.stdout
