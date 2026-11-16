"""One HTTP privacy, nested-tenant and command-header boundary for B routes."""
from uuid import UUID
from collections.abc import Mapping
from rest_framework.views import APIView
from .errors import SubmissionError


class PrivateSubmissionView(APIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant_id, event_id = kwargs.get("makerspace_id"), kwargs.get("pk")
        if event_id is not None:
            from apps.events.models import Event
            from apps.makerspaces.platform import feature_enabled
            event = Event.objects.select_related("makerspace").filter(pk=event_id).first()
            if tenant_id is not None and (event is None or event.makerspace_id != tenant_id):
                raise SubmissionError("not_found", 404)
            # Submissions belong to hackathons alone: off = 404 everywhere (decision 218).
            if event is not None and not feature_enabled(event.makerspace, "events.hackathons"):
                raise SubmissionError("not_found", 404)
        if request.method in ("POST", "PATCH", "DELETE") and isinstance(request.data, Mapping) and "operation_id" in request.data:
            try:
                if UUID(str(request.data["operation_id"])) != UUID(request.headers.get("Idempotency-Key", "")):
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                raise SubmissionError("idempotency_key_mismatch")

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["Vary"] = "Cookie, Authorization"
        response["X-Content-Type-Options"] = "nosniff"
        return response
