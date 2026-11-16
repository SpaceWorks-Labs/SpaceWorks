"""Security and lifetime contract for the bounded Phase 7 claim session."""

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.claim_route_types import Refused
from apps.accounts.claim_routes import CLAIM_ROUTES
from apps.accounts.claim_tokens import ClaimAccessToken, ClaimRefreshToken
from apps.accounts.models import DeviceGrant, User
from apps.events.models import Event, EventRegistration
from apps.makerspaces.models import (
    Makerspace,
    MakerspaceMembership,
    MakerspaceRole,
    MakerspaceWaiver,
    AccountProfile,
)
from apps.payments.models import Payment
from apps.presence.models import PresenceSession
from tests.accounts.claim_helpers_p7 import redeemed_claim, start_claim_presence
from tests.p3_fixbe_helpers import staff_presence

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def bounded_claim_deadline(settings):
    settings.MEMBER_CLAIM_SESSION_TTL_SECONDS = 10 * 60
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5000"]


def test_refresh_rotation_preserves_one_absolute_expiry_forever():
    harness = redeemed_claim("contract-expiry")
    deadline = int(harness.claim.absolute_expires_at.timestamp())
    refresh_ids = []

    for _ in range(3):
        refresh = ClaimRefreshToken(
            harness.claim_client.cookies["refresh_token"].value
        )
        refresh_ids.append(str(refresh["jti"]))
        assert refresh["absolute_expires_at"] == deadline
        assert refresh["exp"] == deadline
        response = harness.claim_client.post(
            "/api/v1/auth/refresh",
            HTTP_X_REFRESH_CSRF="1",
            HTTP_ORIGIN="http://localhost:5000",
        )
        assert response.status_code == 200, response.data
        access = ClaimAccessToken(response.data["access"])
        assert access["absolute_expires_at"] == deadline
        harness.claim_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}"
        )

    harness.claim.refresh_from_db()
    assert int(harness.claim.absolute_expires_at.timestamp()) == deadline
    assert len(set(refresh_ids)) == 3


ROUTE_KWARGS = {
    "devices:member-adapter-watch-start": {"request_id": 1},
    **{f"devices:member-adapter-watch-{name}": {"pk": "00000000-0000-4000-8000-000000000001"}
       for name in ("end", "signal", "frame", "talk")},
    "devices:member-adapter-artifacts": {"request_id": 1},
    "devices:member-adapter-detections": {"request_id": 1},
    "devices:member-adapter-artifact-url": {"pk": "00000000-0000-4000-8000-000000000001"},
    "hardware_requests:member-borrowing-history": {"makerspace_id": "claim"},
    "member-event-history": {"makerspace_id": "claim"},
    "member-profile-handle": {"makerspace_id": "claim"},
    "member-global-profile-timeline-detail": {"pk": 1},
    "member-global-profile-achievement-detail": {"pk": 1},
    "profile-by-account": {"user_id": 1},
    "presence-preferences": {"makerspace_slug": "claim-slug"},
    **{name: {"makerspace_id": "claim"} for name in (
        "member-account-cancel", "member-account-leave", "member-account-membership",
        "member-account-profile", "member-account-sessions", "member-admission",
        "member-admission-export", "member-subject-export-list", "member-verification",
    )},
    "member-account-session-detail": {"makerspace_id": "claim", "session_id": "web:example"},
    # Namespaced L12 routes: the converter fallback reads only the root reverse table.
    "hardware_requests:member-loan-waitlist": {"makerspace_id": "claim"},
    "hardware_requests:member-loan-waitlist-leave": {"makerspace_id": "claim", "pk": 1},
    "hardware_requests:member-request-withdraw": {"makerspace_id": "claim", "pk": 1},
    "member-admission-cancel": {"makerspace_id": "claim", "request_id": 1},
    "member-admission-vouch": {"makerspace_id": "claim", "request_id": 1},
    "member-subject-export-detail": {"makerspace_id": "claim", "job_id": UUID(int=1)},
    "member-subject-export-download": {"makerspace_id": "claim", "job_id": UUID(int=1)},
    "member-payment-document-url": {"makerspace_id": "claim", "document_id": 1},
    "member-event-registration-cancel": {"makerspace_id": "claim", "pk": 1},
    "member-booking-feed-settings": {"makerspace_slug": "claim-slug"},
    "social-oidc": {"slug": "example"},
    "social-provider-detail": {"provider": "google"},
    "device-grant-detail": {"grant_id": UUID(int=1)},
    "membership-invitation-claim": {"pk": 1},
    "membership-invitation-claim-legacy": {"pk": 1},
    "member-waiver-accept": {"makerspace_id": "claim"},
    "member-payment-mobile-intent": {
        "makerspace_id": "claim",
        "payment_id": 1,
    },
    "member-referrals": {"makerspace_id": "claim"},
    "member-collaborative-events": {"makerspace_id": "claim"},
    "member-collaborative-event-register": {
        "makerspace_id": "claim",
        "pk": 1,
    },
    "member-event-checkin-qr": {"makerspace_id": "claim", "pk": 1},
    "member-event-ticket": {"makerspace_id": "claim", "pk": 1},
    "member-event-ticket-png": {"makerspace_id": "claim", "pk": 1},
    # New Lane G routes stay Refused; supply their required URL identities so the
    # existing matrix test reaches authentication and verifies the same 403.
    "member-event-registration-calendar": {"makerspace_id": "claim", "pk": 1},
    "public-event-organization-eligibility": {"makerspace_slug": "claim-slug", "public_token": UUID(int=1)},
    # Booking arrival/pass routes also refuse claims after URL resolution.
    "member-booking-confirmation": {"makerspace_slug": "claim-slug", "public_token": UUID(int=1)},
    "member-booking-confirmation-png": {"makerspace_slug": "claim-slug", "public_token": UUID(int=1)},
    "member-booking-calendar": {"makerspace_slug": "claim-slug", "public_token": UUID(int=1)},
    "member-booking-pass": {"makerspace_slug": "claim-slug", "public_token": UUID(int=1)},
    "member-booking-rotate-checkin": {"makerspace_slug": "claim-slug", "public_token": UUID(int=1)},
    "member-event-calendar": {"makerspace_id": "claim"},
    "member-event-calendar-feed": {"makerspace_id": "claim"},
    "member-event-feedback": {"makerspace_id": "claim", "pk": 1},
    "member-event-certificate-download": {"makerspace_id": "claim", "pk": 1},
    "member-card": {"makerspace_id": "claim"},
    "member-card-photo": {"makerspace_id": "claim"},
    "member-card-preview": {"makerspace_id": "claim"},
    "public-membership-request": {"makerspace_slug": "claim-slug"},
    "public-invitation-request": {"makerspace_slug": "claim-slug"},
}
def _pattern_kwargs(view_name):
    """URL identities for a Refused route the table above does not list, read from its converters:
    the claim's own space for makerspace_id/slug, a UUID or int where the converter wants one."""
    from django.urls import get_resolver
    from django.urls.converters import IntConverter, UUIDConverter

    entries = get_resolver().reverse_dict.getlist(view_name)
    if not entries:
        return {}
    possibilities, _pattern, _defaults, converters = entries[0]
    _format, params = possibilities[0]
    values = {}
    for name in params:
        converter = converters.get(name)
        if name == "makerspace_id":
            values[name] = "claim"
        elif name == "makerspace_slug":
            values[name] = "claim-slug"
        elif isinstance(converter, UUIDConverter):
            values[name] = UUID(int=1)
        elif isinstance(converter, IntConverter):
            values[name] = 1
        else:
            values[name] = "example"
    return values


REFUSED_KEYS = sorted(
    (name, method)
    for (name, method), policy in CLAIM_ROUTES.items()
    if isinstance(policy, Refused)
)


@pytest.mark.parametrize("view_name,method", REFUSED_KEYS)
def test_every_refused_matrix_entry_returns_403(view_name, method):
    harness = redeemed_claim(f"refused-{REFUSED_KEYS.index((view_name, method))}")
    kwargs = {
        key: harness.space.slug if value == "claim-slug" else harness.space.pk if value == "claim" else value
        for key, value in (ROUTE_KWARGS.get(view_name) or _pattern_kwargs(view_name)).items()
    }
    url = reverse(view_name, kwargs=kwargs or None)

    if method in {"POST", "DELETE"}:
        response = harness.claim_client.generic(
            method, url, b"{}", content_type="application/json"
        )
    else:
        response = harness.claim_client.generic(method, url)

    assert response.status_code == 403, (view_name, method, response.data)
    assert not DeviceGrant.objects.filter(user=harness.member).exists()


def event(space, title):
    starts_at = timezone.now() + timedelta(days=1)
    return Event.objects.create(
        makerspace=space,
        title=title,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        is_public=True,
        status=Event.Status.PUBLISHED,
    )


def registration(event_row, harness, *, via):
    return EventRegistration.objects.create(
        event=event_row,
        member=harness.member,
        name=harness.member.display_name,
        email=harness.member.email,
        phone=harness.member.phone,
        registered_via_makerspace=via,
        status=EventRegistration.Status.ATTENDED,
    )


def test_claim_document_metadata_excludes_foreign_host_receipts():
    from apps.payments.documents import issue_receipt

    harness = redeemed_claim("contract-documents")
    local = Payment.objects.create(
        makerspace=harness.space, member=harness.member, created_by=harness.staff,
        subject_type="makerspace_membership", subject_id=harness.membership.pk,
        amount="5.00", currency="usd", status="paid_online",
    )
    local_document = issue_receipt(local)
    foreign_space = Makerspace.objects.create(name="Foreign documents", slug="claim-foreign-documents")
    foreign_registration = registration(event(foreign_space, "Foreign event"), harness, via=harness.space)
    foreign = Payment.objects.create(
        makerspace=foreign_space, member=harness.member, created_by=harness.staff,
        subject_type="event_registration", subject_id=foreign_registration.pk,
        via_makerspace=harness.space, amount="7.00", currency="usd", status="paid_online",
    )
    assert issue_receipt(foreign) is not None
    response = harness.claim_client.get(
        f"/api/v1/member/makerspaces/{harness.space.pk}/payment-documents"
    )
    assert response.status_code == 200, response.data
    assert [row["id"] for row in response.data["results"]] == [local_document.pk]


def payment(space, membership, registration_row, *, via=None):
    return Payment.objects.create(
        makerspace=space,
        subject_type=Payment.SubjectType.EVENT_REGISTRATION,
        subject_id=registration_row.pk,
        member=membership.user,
        via_makerspace=via,
        amount=Decimal("5.00"),
        currency="usd",
        created_by=membership.user,
    )


def test_mixed_ownership_reads_and_checkout_never_return_a_foreign_row():
    harness = redeemed_claim("contract-ownership")
    foreign = Makerspace.objects.create(name="Foreign claim host", slug="foreign-claim-host")
    MakerspaceMembership.objects.create(
        makerspace=foreign,
        user=harness.member,
        role=MakerspaceMembership.Role.CUSTOM,
        assigned_role=MakerspaceRole.objects.get(makerspace=foreign, slug="member"),
    )
    local_registration = registration(event(harness.space, "Local event"), harness, via=harness.space)
    foreign_registration = registration(event(foreign, "Foreign event"), harness, via=harness.space)
    local_payment = payment(harness.space, harness.membership, local_registration)
    foreign_payment = payment(foreign, harness.membership, foreign_registration, via=harness.space)
    AccountProfile.objects.create(user=harness.membership.user, is_visible=True, show_events=True)

    base = f"/api/v1/member/makerspaces/{harness.space.pk}"
    activity = harness.claim_client.get(f"{base}/activity")
    usage = harness.claim_client.get(f"{base}/my-usage")
    profile = harness.claim_client.get(f"{base}/profile")
    detail = harness.claim_client.get(f"{base}/directory/{harness.membership.pk}")
    history = harness.claim_client.get(f"{base}/payments")
    foreign_checkout = harness.claim_client.post(
        f"{base}/payments/{foreign_payment.pk}/checkout"
    )

    assert activity.status_code == profile.status_code == detail.status_code == 200
    assert [row["event_title"] for row in activity.data["event_registrations"]] == ["Local event"]
    assert usage.status_code == 200, usage.data
    assert usage.data["usage_available"] is True
    assert usage.data["events"]["attended_count"] == 1
    assert usage.data["payments"]["outstanding_by_currency"] == {"usd": "5.00"}
    # Registrations are read by PROVENANCE (decision on member history): the foreign event was registered VIA
    # this space, so it counts here; the row listing above still shows only this host's own event.
    assert profile.data["activity"]["events_registered"] == 2
    assert [row["title"] for row in detail.data["activity"]["recent_attended_events"]] == ["Local event"]
    assert [row["id"] for row in history.data] == [local_payment.pk]
    assert foreign_checkout.status_code == 404


def test_revocation_rejects_the_live_access_token_and_ends_only_claim_presence():
    harness = redeemed_claim("contract-revoke")
    ordinary = staff_presence(harness.member, harness.space, 60)
    claim_presence = start_claim_presence(harness, 60)
    ordinary.refresh_from_db()
    # A new account session supersedes the earlier session. Revocation must not
    # rewrite its durable end metadata or touch another person's active session.
    assert ordinary.end_reason == "superseded"
    ordinary_end = ordinary.ended_at
    other = User.objects.create_user(username="ordinary-revoke-neighbour")
    MakerspaceMembership.objects.create(
        user=other, makerspace=harness.space, role="custom",
        assigned_role=MakerspaceRole.objects.get(makerspace=harness.space, slug="member"),
    )
    other_presence = staff_presence(other, harness.space, 60)
    assert claim_presence.ended_at is None

    revoked = harness.staff_client.post(
        f"/api/v1/admin/makerspaces/{harness.space.pk}/member-claim-codes/{harness.claim.pk}/revoke"
    )
    next_request = harness.claim_client.get("/api/v1/auth/me")

    assert revoked.status_code == 200
    assert next_request.status_code == 401
    ordinary.refresh_from_db()
    claim_presence.refresh_from_db()
    assert ordinary.ended_at == ordinary_end
    assert ordinary.end_reason == "superseded"
    other_presence.refresh_from_db()
    assert other_presence.ended_at is None
    assert claim_presence.ended_at is not None
    assert claim_presence.end_reason == PresenceSession.EndReason.CLAIM_REVOKED


def test_claim_session_cannot_accept_a_waiver():
    harness = redeemed_claim("contract-waiver")
    MakerspaceWaiver.objects.create(
        makerspace=harness.space, is_active=True, version=1, body="Desk terms"
    )

    response = harness.claim_client.post(
        f"/api/v1/member/makerspaces/{harness.space.pk}/waiver/accept"
    )

    assert response.status_code == 403
    harness.membership.refresh_from_db()
    assert harness.membership.accepted_waiver_id is None
    assert harness.membership.waiver_accepted_at is None
