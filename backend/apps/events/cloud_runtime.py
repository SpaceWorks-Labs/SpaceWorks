"""Query-free programme composition and fixed scanner/probe policy.

I installs EV's real SubmissionRuntime/boundary before discovery. Missing
lifecycle adapters are readiness failures, never successful empty sweeps.
"""
from dataclasses import dataclass
import sys
from typing import Callable

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.operations.cloud_jobs.contracts import JobsUnavailable


@dataclass(frozen=True)
class EventCloudRuntime:
    # Each callback owns its live/retained discovery, source/PII fences, cursors,
    # row locks, audit writes and object deletion receipts. No ORM here bypasses it.
    asset_lifecycle: Callable
    programme_receipts: Callable
    stage_file_retention: Callable


_runtime = None


def install_runtime(value):
    global _runtime
    if not isinstance(value, EventCloudRuntime) or any(not callable(callback) for callback in (
        value.asset_lifecycle, value.programme_receipts, value.stage_file_retention,
    )):
        raise ImproperlyConfigured("Invalid Events cloud runtime")
    if _runtime is not None and _runtime is not value:
        raise ImproperlyConfigured("Events cloud runtime already installed")
    _runtime = value


def runtime():
    if _runtime is None:
        raise JobsUnavailable("events_cloud_runtime_unavailable")
    return _runtime


def scan_options():
    policy = getattr(settings, "UPLOAD_SCAN_POLICY", "none")
    if policy not in {"none", "clamav"}:
        raise ImproperlyConfigured("UPLOAD_SCAN_POLICY must be none or clamav")
    if policy == "none":
        return {"backend": "none"}
    host = getattr(settings, "CLAMD_HOST", "")
    port = getattr(settings, "CLAMD_PORT", 3310)
    maximum = getattr(settings, "CLAMD_MAX_SCAN_BYTES", 2147483648)
    timeout = getattr(settings, "CLAMD_TIMEOUT_SECONDS", 5)
    if (not isinstance(host, str) or not host.strip() or "://" in host
            or type(port) is not int or not 1 <= port <= 65535
            or type(maximum) is not int or not 1 <= maximum <= 2147483648
            or type(timeout) is not int or not 1 <= timeout <= 30):
        raise ImproperlyConfigured("Invalid private ClamAV configuration")
    # EV's current scanning.scan has a fixed five-second socket timeout. Refuse
    # incompatible settings until I/EV prepares its explicit timeout parameter.
    if timeout != 5:
        raise ImproperlyConfigured("The installed scanner adapter requires a five-second timeout")
    return {"backend": "clamav", "host": host, "port": port, "max_scan_bytes": maximum}


def sandbox_command():
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
        return ()
    return (sys.executable, "-m", "apps.events.submissions.probe_sandbox")


def video_validation_availability():
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
        return {"available": False, "reason": "video_validation_unavailable_in_free_profile"}
    return {"available": True, "reason": ""}
