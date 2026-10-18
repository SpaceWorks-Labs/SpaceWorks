"""G installs these guards in every legacy registration mutation boundary.

An enabled config is authoritative even when its capability becomes unavailable:
falling back to ordinary register/approve would bypass application consent/review.
"""
from .admission_errors import fail
from .admission_models import HackathonApplication, HackathonConfig


class CanonicalRegistrationBridge:
    """The production port delegates all writes to the existing registration domain."""

    def create_pending_locked(self, **kwargs):
        from apps.events.services_registration_admission import create_pending_locked
        return create_pending_locked(**kwargs)

    def transition_locked(self, **kwargs):
        from apps.events.services_registration_admission import transition_locked
        return transition_locked(**kwargs)

    def mirror_answers_locked(self, **kwargs):
        from apps.events.services_registration_admission import mirror_answers_locked
        return mirror_answers_locked(**kwargs)


def enabled_for(event_id):
    return HackathonConfig.objects.filter(event_id=event_id, enabled=True).exists()


def requires_admission(event_id):
    return enabled_for(event_id) or HackathonApplication.objects.filter(event_id=event_id).exists()


def require_ordinary_registration(event):
    if requires_admission(event.pk):
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
