"""Response-side channel analytics: the ``api_client`` channel and key-flow completions.

Web and phone calls are counted where they authenticate (``channel_activity``), which also leaves
the channel on the request. Signed API clients authenticate in ``FrontendHMACMiddleware`` before
the route is resolved, so their area is only known once the view has run: count on the way out.
Browser ``X-Client-Id`` calls are the web build itself, never the ``api_client`` channel.

A *flow completion* is a successful POST to one of the key member/staff flows below, counted under
the area ``flow:<name>`` for the channel that made it. Counts only; nothing identifies a person.
"""

from .channel_usage import record_call

FLOW_ROUTES = {
    "request-submit": "request_submitted",
    "request-issue": "item_issued", "direct-loans": "item_issued", "public-tool-checkout": "item_issued",
    "request-return": "item_returned", "direct-loan-return": "item_returned",
    "public-tool-return": "item_returned", "guest-admin-request-return": "item_returned",
    "member-payment-checkout": "payment_started", "member-payment-mobile-intent": "payment_started",
    "pay-link-checkout": "payment_started",
    "member-booking-checkout": "booking_made",
    "public-event-register": "event_registered", "member-collaborative-event-register": "event_registered",
    "member-machine-jobs": "machine_job_requested", "public-machine-job-submit": "machine_job_requested",
}


class ChannelUsageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            channel, space_id = getattr(request, "sw_channel", None), getattr(request, "sw_channel_space", None)
            client = getattr(request, "api_client", None)
            if channel is None and client is not None and getattr(request, "api_client_signature_verified", False):
                channel, space_id = "api_client", getattr(client, "makerspace_id", None)
                record_call(channel, request, space_id)
            elif channel is None:
                from apps.apiclients.models_tokens import PersonalAccessToken
                if isinstance(getattr(request, "auth", None), PersonalAccessToken):
                    channel, space_id = "api_client", None
                    record_call(channel, request, space_id)
            flow = FLOW_ROUTES.get(getattr(getattr(request, "resolver_match", None), "url_name", None))
            if channel and flow and request.method == "POST" and 200 <= response.status_code < 300:
                record_call(channel, request, space_id, area=f"flow:{flow}")
        except Exception:  # noqa: BLE001 -- analytics never fails a response
            pass
        return response
