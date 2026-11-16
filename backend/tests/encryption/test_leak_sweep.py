"""Raw-column regression sweep for every scoped PII registry entry."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.contrib.admin.sites import AdminSite
from django.db import connection
from django.test import override_settings
from django.utils import timezone

from apps.bookings.models import BookableSpace, Booking
from apps.bookings.models_broadcasts import BookingBroadcast
from apps.bookings.models_departure import BookingDepartureEvent
from apps.encryption.crypto import is_envelope
from apps.encryption.registry import ALL_FIELDS
from apps.events.models import (
    Event,
    EventAttendanceCertificate,
    EventFeedbackResponse,
    EventFeedbackSurvey,
    EventRegistration,
)
from apps.events.models_broadcasts import EventBroadcast
from apps.hardware_requests.models import HardwareRequest
from apps.integrations.admin_email_logs import EmailLogAdmin
from apps.integrations.models import EmailLog, MessagingConsent
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint, NotificationEndpointChallenge
from apps.notifications.models import MemberBroadcast, NotificationInboxRow
from apps.makerspaces.models import InvitationRequest, Makerspace, MemberCard, MembershipRequest
from apps.devices.models import Device, DeviceCommand, PrinterJob
from apps.machines.models import (
    Machine,
    MachineServiceRequest,
    MachineType,
    MachineUsageEntry,
    ServiceBucket,
)
from tests.encryption.conftest import enabled_encryption
from tests.encryption import leak_sweep_programme as programme
from tests.encryption import leak_sweep_reimbursements as reimbursements
from tests.encryption import leak_sweep_release2 as release2
from tests.event_reimbursements.conftest import make_world  # noqa: F401 (fixture)
from tests.events.programme.answer_derivations.conftest import (  # noqa: F401 (fixture)
    age_world, create_subject, insert, prepare,
)

# Events programme models (and the registration answers document) are written through
# leak_sweep_programme: real parent graphs, sentinel written at INSERT.
PROGRAMME_LABELS = {item.model_label for item in ALL_FIELDS
                    if item.model_label.startswith("events.") and not reimbursements.covers(item.model_label)
                    and item.model_label not in {
                        "events.EventRegistration", "events.EventBroadcast",
                        "events.EventFeedbackResponse", "events.EventAttendanceCertificate",
                        "events.EventIdCard"}}

pytestmark = pytest.mark.django_db


def _objects():
    stamp = uuid4().hex[:10]
    space = Makerspace.objects.create(name="Sweep", slug=f"sweep-{stamp}")
    user = get_user_model().objects.create_user(username=f"sweep-{stamp}")
    now = timezone.now()
    event = Event.objects.create(makerspace=space, title="Sweep event", starts_at=now, ends_at=now + timedelta(hours=1))
    bookable = BookableSpace.objects.create(makerspace=space, name="Sweep bench")
    machine_type = MachineType.objects.create(makerspace=space, slug=f"sweep-{stamp}", name="Sweep machine")
    machine = Machine.objects.create(makerspace=space, machine_type=machine_type, name="Sweep machine")
    service_bucket = ServiceBucket.objects.create(machine=machine, name="Sweep service")
    registration = EventRegistration.objects.create(
        event=event, name="Base", email=f"base-{stamp}@example.test", phone="1",
    )
    survey = EventFeedbackSurvey.objects.create(
        event=event, title="Sweep survey",
        questions=[{"id": "q1", "label": "Rating", "type": "number", "options": [], "required": True}],
    )
    # event_feedback_response_mode_matches_identity: a response carries its registration
    # only when a certificate was requested; an anonymous one must stay unattributed.
    response = EventFeedbackResponse.objects.create(
        survey=survey, registration=registration, answers_snapshot="{}",
        certificate_requested=True,
    )
    device = Device.objects.create(makerspace=space, kind="printer", name="Sweep printer")
    command = DeviceCommand.objects.create(makerspace=space, device=device, device_key_version=0)
    booking = Booking.objects.create(space=bookable, name="Base", email=f"booking-{stamp}@example.test",
        phone="1", starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, hours=1))
    configuration = ChannelConfiguration.objects.create(makerspace=space, channel="telegram", provider="telegram")
    endpoint = NotificationEndpoint.objects.create(makerspace=space, user=user, configuration=configuration,
        channel="telegram", provider="telegram", destination="private-destination", provider_subject="private-subject",
        identity_digest=uuid4().hex, integration_identity="sweep-install", integration_generation=1,
        verified_at=now, consented_at=now, consent_version="v1")
    from apps.maintenance.models import IssueReport, TechnicianContact
    return {
        # L16: a contractor's contact details and a reporter's name and email.
        "maintenance.TechnicianContact": TechnicianContact.objects.create(makerspace=space, kind="external", name="Sweep"),
        "maintenance.IssueReport": IssueReport.objects.create(
            makerspace=space, area="machines", subject_type="machine", machine=machine, source="staff",
            title="Sweep", description="Sweep issue"),
        "bookings.BookingDepartureEvent": BookingDepartureEvent.objects.create(
            makerspace=space, booking=booking, actor=user, outcome="all_good", source="member"),
        "integrations.NotificationEnvelope": NotificationEnvelope.objects.create(
            makerspace=space, recipient=user, feature="bookings", stream="bookings", event="confirmed",
            audience="requester", source_kind="bookings.booking", source_id=str(booking.pk), dedup_key=uuid4().hex),
        "integrations.NotificationEndpoint": endpoint,
        "integrations.NotificationEndpointChallenge": NotificationEndpointChallenge.objects.create(
            makerspace=space, user=user, configuration=configuration, integration_identity="sweep-install",
            integration_generation=1, code_digest=uuid4().hex, expires_at=now + timedelta(minutes=10),
            consented_at=now, consent_version="v1"),
        "integrations.MessagingConsent": MessagingConsent.objects.create(
            makerspace=space, user=user, channel="sms", action="opted_in",
            phone_e164="+14155552671", phone_verified_at=now, source="member_settings",
        ),
        "devices.PrinterJob": PrinterJob.objects.create(
            makerspace=space, device=device, command=command, machine=machine,
            machine_id_snapshot=machine.pk, machine_name=machine.name,
            service_request_id_snapshot=1, service_request_name="Sweep job",
            external_job_id=f"sweep-{stamp}",
        ),
        "makerspaces.MembershipRequest": MembershipRequest.objects.create(
            makerspace=space, user=user, kind="request", state="requested"
        ),
        "notifications.MemberBroadcast": MemberBroadcast.objects.create(
            makerspace=space, created_by=user, title="Base", body="Base announcement"),
        "notifications.NotificationInboxRow": NotificationInboxRow.objects.create(
            makerspace=space, user=user, event_key=uuid4(), feature="bookings", event="confirmed", title="Base"),
        "hardware_requests.HardwareRequest": HardwareRequest.objects.create(makerspace=space, requester=user, requester_username=user.username),
        "events.EventRegistration": registration,
        "events.EventBroadcast": EventBroadcast.objects.create(
            event=event, makerspace=space, created_by=user,
            subject="Base subject", body="Base message", statuses=[registration.status],
        ),
        "bookings.BookingBroadcast": BookingBroadcast.objects.create(
            space=bookable, makerspace=space, created_by=user,
            subject="Base subject", body="Base message", statuses=["confirmed"],
            window_start=now, window_end=now + timedelta(days=1),
        ),
        "events.EventFeedbackResponse": response,
        "events.EventAttendanceCertificate": EventAttendanceCertificate.objects.create(
            response=response, registration=registration, revision=1,
            recipient_name="Base", event_title="Sweep event",
            event_starts_at=now, event_ends_at=now + timedelta(hours=1),
            issuer_name="Sweep", object_key=f"certificates/sweep-{stamp}.pdf",
        ),
        "bookings.Booking": booking,
        "machines.MachineServiceRequest": MachineServiceRequest.objects.create(bucket=service_bucket, requester=user, title="Sweep service"),
        "machines.MachineUsageEntry": MachineUsageEntry.objects.create(machine=machine, logged_by=user),
        "makerspaces.MemberCard": MemberCard.objects.create(makerspace=space, card_number=1, printed_name="Base"),
        "makerspaces.InvitationRequest": InvitationRequest.objects.create(makerspace=space, name="Base", email=f"invite-{stamp}@example.test", phone="1"),
        "integrations.EmailLog": EmailLog.objects.create(makerspace=space, to_email=f"mail-{stamp}@example.test", subject="Base", text_body="", html_body=""),
        **_l3_objects(space, user, event, registration, now, stamp),
    }


def _l3_objects(space, user, event, registration, now, stamp):
    """Release 2 L3: one row per card model holding scoped PII."""
    from apps.card_designs.models import CardHolderExtras
    from apps.events.models import EventIdCard
    from apps.id_programmes.models import IdProgramme, IdProgrammeCard
    from apps.organizations.models import Organization
    card = MemberCard.objects.create(makerspace=space, card_number=2, printed_name="Base extras")
    organization = Organization.objects.create(name="Sweep org", slug=f"sweep-org-{stamp}")
    programme = IdProgramme.objects.create(organization=organization, makerspace=space, name="Sweep IDs",
                                           slug=f"sweep-ids-{stamp}", id_prefix="SWP")
    return {
        "card_designs.CardHolderExtras": CardHolderExtras.objects.create(makerspace=space, member_card=card),
        "id_programmes.IdProgrammeCard": IdProgrammeCard.objects.create(programme=programme, makerspace=space,
                                                                         name="Base"),
        "events.EventIdCard": EventIdCard.objects.create(event=event, makerspace=space, registration=registration,
                                                         person=user, printed_name="Base", valid_until=now),
    }


def _sentinel(item):
    token = f"SENTINEL-{item.model_label.replace('.', '-')}-{item.field_name}-{uuid4().hex[:8]}"
    return f"{token.lower()}@example.test" if "email" in item.field_name else token


# Mandatory finance key preparation must also precede pytest's outer transaction.
_TRANSACTIONAL_LABELS = {"payments.DonorTaxDetail", "events.HackathonPrizeClaim", *release2.KEYED_LABELS}
_SWEEP_ITEMS = [pytest.param(item, marks=pytest.mark.django_db(transaction=True))
                if reimbursements.covers(item.model_label) or item.model_label in _TRANSACTIONAL_LABELS
                else item for item in ALL_FIELDS]


@pytest.mark.parametrize("item", _SWEEP_ITEMS, ids=lambda item: f"{item.model_label}.{item.field_name}")
def test_every_mapped_value_is_an_envelope_and_not_a_raw_database_leak(item, caplog, request):
    edge = (item.model_label, item.field_name)
    derivation = item.model_label == "events.EventAnswerDerivation"
    # age_world enables encryption itself; nesting a second context would rotate the
    # search key under the already-bound generation, so it is used on its own.
    world = request.getfixturevalue("age_world") if derivation else None
    from contextlib import nullcontext
    with nullcontext() if derivation else enabled_encryption():
        token = _sentinel(item)
        value = {"answer": token} if edge in programme.DOCUMENTS else token
        if item.model_label == "events.EventAnswerDerivation":
            # Source DOB evidence is only ever written by the prepared derivation workflow.
            from apps.events.answer_derivations.models import EventAnswerDerivation
            from apps.events.contracts.subjects import SubjectKind
            _, subject = create_subject(world, SubjectKind.REGISTRATION)
            token = "1997-03-04"
            canonical = insert(world, subject, prepare(world, subject, dob=token))
            row = EventAnswerDerivation.objects.get(pk=canonical[0]["derivation_id"])
            value = None
        elif reimbursements.covers(item.model_label):
            # Reimbursement, payout and stage-form rows come from one real journey (see module).
            row, value = reimbursements.create(item, token, request)
            assert getattr(type(row).objects.get(pk=row.pk), item.field_name) == value
            assert getattr(row, item.field_name) == value
            value = None
        elif item.model_label in PROGRAMME_LABELS or edge in programme.DOCUMENTS:
            from apps.events.submissions.pii import prepare_documents
            w = programme.world()
            # Programme documents encrypt and decrypt only under prepared tenant keys.
            with prepare_documents(w.event.pk):
                row = programme.create(item.model_label, item.field_name, value, w)
                assert getattr(type(row).objects.get(pk=row.pk), item.field_name) == value
                assert getattr(row, item.field_name) == value
            value = None
        elif item.model_label in release2.SPACE_LABELS:
            # Release-2 space rows are written at INSERT (see leak_sweep_release2).
            if item.model_label in release2.KEYED_LABELS:
                from apps.encryption.preparation import prepare_tenants
                space = release2.new_space()
                with prepare_tenants((space.pk,)):
                    row = release2.create_space_row(item.model_label, item.field_name, value, space)
                    assert getattr(type(row).objects.get(pk=row.pk), item.field_name) == value
            else:
                row = release2.create_space_row(item.model_label, item.field_name, value)
                assert getattr(type(row).objects.get(pk=row.pk), item.field_name) == value
            value = None
        else:
            row = _objects()[item.model_label]
        if value is None:
            pass
        elif item.model_label == "bookings.BookingDepartureEvent":
            # Departure remarks are immutable evidence: exercise encryption on
            # INSERT, never bypass the append-only model/database guards.
            row = BookingDepartureEvent.objects.create(makerspace=row.makerspace,
                booking=row.booking, actor=row.actor, outcome="issue", source="member", remark=value)
        elif item.model_label == "integrations.MessagingConsent":
            # Consent history is append-only: exercise the encrypted INSERT,
            # without invoking the maintenance-only UPDATE exception.
            row = MessagingConsent.objects.create(
                makerspace=row.makerspace, user=row.user, channel=row.channel,
                action=row.action, source=row.source, phone_verified_at=row.phone_verified_at,
                **{item.field_name: value},
            )
        elif item.model_label == "machines.MachineUsageEntry":
            # The typed usage ledger is append-only. Its scoped PII must be
            # encrypted at creation rather than through an invalid update.
            row = MachineUsageEntry.objects.create(
                machine=row.machine,
                logged_by=row.logged_by,
                **{item.field_name: value},
            )
        elif item.model_label == "events.EventFeedbackResponse":
            # Feedback answers are an immutable snapshot. Written anonymously here so the
            # identity-mode check constraint holds without a second registration.
            row = EventFeedbackResponse.objects.create(
                survey=row.survey,
                registration=None,
                certificate_requested=False,
                **{item.field_name: value},
            )
        elif item.model_label == "events.EventAttendanceCertificate":
            # Certificate issuance snapshots are immutable, uniq_live_event_certificate
            # allows one non-revoked certificate per registration, and a database trigger
            # refuses a pending -> revoked shortcut. So the sentinel certificate is issued
            # for a FRESH registration rather than contorting the base row.
            stamp = uuid4().hex[:8]
            fresh = EventRegistration.objects.create(
                event=row.registration.event,
                name="Sweep",
                email=f"sweep-cert-{stamp}@example.test",
                phone="1",
            )
            fresh_response = EventFeedbackResponse.objects.create(
                survey=row.response.survey,
                registration=fresh,
                certificate_requested=True,
                answers_snapshot="{}",
            )
            row = EventAttendanceCertificate.objects.create(
                response=fresh_response,
                registration=fresh,
                revision=1,
                event_title=row.event_title,
                event_starts_at=row.event_starts_at,
                event_ends_at=row.event_ends_at,
                issuer_name=row.issuer_name,
                object_key=f"certificates/sweep-{stamp}.pdf",
                **{item.field_name: value},
            )
        else:
            setattr(row, item.field_name, value)
            row.save(update_fields=[item.field_name])
        if value is not None:
            assert getattr(row, item.field_name) == value
        if item.model_label == "integrations.MessagingConsent":
            row.refresh_from_db()
        if value is not None:
            assert getattr(row, item.field_name) == value
        column = row._meta.get_field(item.field_name).column
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT "{column}" FROM "{row._meta.db_table}" WHERE id = %s', [row.pk])
            raw = cursor.fetchone()[0]
            assert raw.startswith("pii:gcm:v1:")
            assert is_envelope(raw)
            for field in ALL_FIELDS:
                model = __import__("django.apps", fromlist=["apps"]).apps.get_model(field.model_label)
                db_column = model._meta.get_field(field.field_name).column
                cursor.execute(f'SELECT "{db_column}" FROM "{model._meta.db_table}"')
                assert all(token not in str(cell) and token.lower() not in str(cell).lower() for (cell,) in cursor.fetchall())
        assert token not in caplog.text


def test_email_log_platform_contract_and_admin_surface_remain_pii_safe(monkeypatch):
    from apps.integrations.dispatch import dispatch_email

    with enabled_encryption():
        monkeypatch.setattr("apps.integrations.dispatch._deliver", lambda log: log)
        platform = dispatch_email(to_email="platform@example.test", subject="secret", text_body="body", sync=True)
        makerspace = _objects()["integrations.EmailLog"]
        with connection.cursor() as cursor:
            cursor.execute('SELECT "to_email", "subject", "text_body" FROM "integrations_emaillog" WHERE id = %s', [makerspace.pk])
            assert all(not value or is_envelope(value) for value in cursor.fetchone())
            cursor.execute('SELECT "to_email", "subject", "text_body" FROM "integrations_emaillog" WHERE id = %s', [platform.pk])
            assert cursor.fetchone() == ("", "Platform email", "")
        admin = EmailLogAdmin(EmailLog, AdminSite())
        assert "to_email" not in admin.search_fields and "subject" not in admin.search_fields
        assert not getattr(EmailLogAdmin.recipient_display, "admin_order_field", None)


def test_flag_off_platform_logs_preserve_values_and_historical_redaction():
    with override_settings(PII_ENCRYPTION_ENABLED=False):
        ordinary = EmailLog.objects.create(to_email="reset@example.test", subject="Reset", text_body="body")
        historical = EmailLog.objects.create(to_email="", subject="Platform email", text_body="", html_body="")
        ordinary.refresh_from_db()
        historical.refresh_from_db()
        assert (ordinary.to_email, ordinary.subject) == ("reset@example.test", "Reset")
        assert (historical.to_email, historical.subject, historical.text_body) == ("", "Platform email", "")
