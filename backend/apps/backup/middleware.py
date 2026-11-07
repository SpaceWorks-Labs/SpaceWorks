from django.db import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.urls import Resolver404, resolve
from django.utils.translation import gettext

from config.locale_resolution import early_response_locale, finalize_response

from apps.backup.models import DeploymentRecoveryState
from apps.backup.route_policy import route_allowed


class DeploymentRecoveryGateMiddleware:
    """Global, default-deny request gate for quiescence and disaster recovery.

    This reads the mode from the database on EVERY request, deliberately and without a cache.
    A cache was written and removed: it bought an amortised query at the cost of a staleness
    window in which a deployment that had just been quarantined would keep serving traffic,
    which is the one failure this gate exists to prevent. It also made the per-request query
    count depend on cache warmth, which broke three query-count tests that capture a count and
    then assert equality -- the first request paid for the lookup and later ones did not.

    The cost is one primary-key lookup on a single-row table, served from shared buffers. If
    that ever needs optimising, the answer is a mechanism with no staleness window (a
    connection-level or LISTEN/NOTIFY-driven invalidation), not a TTL.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            mode = self._load_mode()
        except (OperationalError, ProgrammingError):
            return self._refused("unavailable", request)
        if mode == DeploymentRecoveryState.Mode.NORMAL:
            from apps.operations.cloud_runtime import managed, writer
            if managed() and request.path_info.rstrip("/") not in {"/api/v1/health", "/api/v1/health/readiness"}:
                from apps.backup.managed.admission import ManagedAdmissionError
                try:
                    with writer("web"):
                        response = self.get_response(request)
                        if getattr(response, "streaming", False):
                            response.streaming_content = _managed_stream(response.streaming_content)
                        return response
                except ManagedAdmissionError:
                    return self._refused("managed_admission_refused", request)
            if not managed() and request.path_info.rstrip("/") not in {"/api/v1/health", "/api/v1/health/readiness"}:
                from apps.operations.cloud_runtime import check
                from apps.backup.managed.admission import ManagedAdmissionError
                try:
                    check()
                except (ManagedAdmissionError, OperationalError, ProgrammingError):
                    return self._refused("mode_binding_unavailable", request)
            return self.get_response(request)
        try:
            view_name = resolve(request.path_info).view_name or ""
        except Resolver404:
            return self._refused(mode, request)
        if not route_allowed(mode, view_name, request.method):
            return self._refused(mode, request)
        return self.get_response(request)

    @staticmethod
    def _load_mode():
        state = DeploymentRecoveryState.objects.only("mode").filter(pk=1).first()
        # The singleton is a routing gate, not optional configuration. Treating an
        # absent row as NORMAL would make a partially restored sibling serve before
        # Phase D7 has installed TARGET_IMPORT and completed pointer cutover.
        return state.mode if state else "unavailable"

    @staticmethod
    def _refused(mode, request):
        # This gate sits OUTSIDE the locale reset boundary (it must stay first), so its one
        # answer is rendered inside the same pre-auth resolution's scoped override.
        with early_response_locale(request):
            detail = (
                gettext("This deployment is in recovery quarantine. Only recovery routes are available.")
                if mode == DeploymentRecoveryState.Mode.QUARANTINED
                else (
                    gettext("This deployment is being prepared as a non-routable import target.")
                    if mode == DeploymentRecoveryState.Mode.TARGET_IMPORT
                    else gettext("This deployment is temporarily unavailable for restore.")
                )
            )
            response = JsonResponse({"detail": detail, "code": f"deployment_{mode}"}, status=503)
            return finalize_response(response)


def _managed_stream(content):
    from apps.operations.cloud_runtime import writer
    with writer("web") as check:
        for chunk in content:
            check()
            yield chunk
