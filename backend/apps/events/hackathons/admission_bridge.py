"""G installs these guards in every legacy registration mutation boundary.

An enabled config is authoritative even when its capability becomes unavailable:
falling back to ordinary register/approve would bypass application consent/review.
"""
from .admission_errors import fail
from .admission_models import HackathonApplication, HackathonConfig


def enabled_for(event_id):
    return HackathonConfig.objects.filter(event_id=event_id, enabled=True).exists()


def require_ordinary_registration(event):
    if enabled_for(event.pk):
        from .admission_transactions import require_programme
        require_programme(event)
        fail("hackathon_application_required", "Apply through this event's application form.")


def require_ordinary_transition(registration):
    if enabled_for(registration.event_id) or HackathonApplication.objects.filter(registration=registration).exists():
        fail("hackathon_admission_required", "Use the application review and RSVP workflow for this registration.")


def assert_registration_mapping(*, application_id):
    app = HackathonApplication.objects.select_related("registration").get(pk=application_id)
    if app.state == "draft":
        return
    expected = {"submitted": ("pending_approval",), "offered": ("pending_approval",),
                "waitlisted": ("waitlisted",), "confirmed": ("registered", "attended"),
                "rejected": ("rejected",), "declined": ("cancelled",),
                "expired": ("cancelled",), "withdrawn": ("cancelled",)}
    if not app.registration_id or app.registration.status not in expected.get(app.state, ()):
        fail("admission_mapping_conflict", "The application and registration need staff reconciliation.")
