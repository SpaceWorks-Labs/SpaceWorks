"""Bounded HTTP measurements; no paths, tenants, credentials or query strings."""
from time import perf_counter
import logging

from django.conf import settings
from django.urls import resolve
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client import multiprocess

logger = logging.getLogger(__name__)

REQUESTS = Counter(
    "spaceworks_http_requests_total", "Completed HTTP requests.",
    ("route", "method", "status"),
)
LATENCY = Histogram(
    "spaceworks_http_request_duration_seconds", "HTTP response construction latency.",
    ("route", "method"), buckets=(.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10),
)
METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})


def route_label(request):
    """Django's compiled route is finite even for malformed IDs and bearer URLs."""
    match = getattr(request, "resolver_match", None)
    if match is None:
        # Signature/host middleware may refuse before Django dispatch resolves
        # the view. Resolve only to a compiled template, never label raw paths.
        path = getattr(request, "path_info", "")
        if path:
            try:
                match = resolve(path)
            except Exception:
                pass
    route = getattr(match, "route", None)
    return str(route) if route else "unmatched"


def exposition():
    if getattr(settings, "PROMETHEUS_MULTIPROC_DIR", ""):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry).decode("utf-8")
    registry = CollectorRegistry()
    registry.register(REQUESTS)
    registry.register(LATENCY)
    return generate_latest(registry).decode("utf-8")


class RouteMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "ROUTE_METRICS_ENABLED", False):
            return self.get_response(request)
        start = perf_counter()
        status = 500
        try:
            response = self.get_response(request)
            status = response.status_code
            return response
        finally:
            try:
                method = request.method if request.method in METHODS else "OTHER"
                status = str(status) if 100 <= status <= 599 else "other"
                route = route_label(request)
                REQUESTS.labels(route, method, status).inc()
                LATENCY.labels(route, method).observe(max(0, perf_counter() - start))
            except Exception:
                # Optional telemetry must not turn a valid response or an existing
                # refusal into a server error when its worker directory fails.
                logger.exception("route_metrics_collection_failed")
