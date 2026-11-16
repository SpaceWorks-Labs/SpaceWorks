"""The HTTP side of the A1 context boundary (one binding per request, reset in finally)."""

import logging

from .boundary import request_binding
from .context import activate, bind

logger = logging.getLogger(__name__)


class TenantRlsBoundaryMiddleware:
    """Opens an unbound scope for the request and binds it once the route is resolved.

    Queries made before ``process_view`` (session, authentication, other middleware) and
    after the response leaves (streamed bodies) run open. Leaving the scope always resets
    the binding and the connection state, even when the view raised.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with bind(None):
            try:
                return self.get_response(request)
            finally:
                from .report import flush
                flush(label=getattr(getattr(request, "resolver_match", None), "url_name", "") or "")

    def process_view(self, request, view_func, view_args, view_kwargs):
        try:
            binding = request_binding(request)
        except Exception:  # resolution is advisory; an unresolved route stays open
            logger.exception("tenant_rls_request_binding_failed")
            binding = None
        activate(binding)
        return None
