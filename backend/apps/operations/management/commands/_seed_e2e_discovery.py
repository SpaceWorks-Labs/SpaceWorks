"""Real discovery and member fixtures for the browser accessibility gate."""

from datetime import timedelta

from django.utils import timezone

from apps.bookings.models import BookableSpace
from apps.events.models import Event
from apps.makerspaces.module_install import install_module


def seed_discovery(makerspace, actor, member):
    for key in ("events", "bookings", "membership"):
        install_module(makerspace, key, actor=actor)
    member.email_verified_at = timezone.now()
    member.save(update_fields=["email_verified_at"])
    makerspace.theme_config = {"primary_color": "#f3c3dd", "accent_color": "#5a1633"}
    makerspace.branding_config = {
        "support_email": "help@example.com",
        "support_url": "https://example.com/support",
    }
    makerspace.save(update_fields=["theme_config", "branding_config"])
    starts_at = timezone.now() + timedelta(days=7)
    event = Event.objects.create(
        makerspace=makerspace, title="E2E Public Workshop", description="Learn together.",
        starts_at=starts_at, ends_at=starts_at + timedelta(hours=2),
        is_public=True, status=Event.Status.PUBLISHED, capacity=10, created_by=actor,
    )
    space = BookableSpace.objects.create(
        makerspace=makerspace, name="E2E Public Bench", is_public=True, capacity=2,
    )
    return {"event_title": event.title, "bookable_space": space.name}


def seed_machine_journey(makerspace, actor, member):
    """Idempotent, tenant-local fixture for machine-journey.spec.ts on the standard seed.

    The member owes 30 * 2 + 5 = 65 at quote and 20 * 2 + 5 = 45 at
    completion. Disable optional price overrides/discounts/tax in this disposable
    space so those totals describe exactly the policy the browser approves.
    """
    from apps.audit import services as audit
    from apps.machines.models import Machine, MachineType, ServiceQueue, MakerspaceMachineTypePricing
    from apps.machines.models_policy import MakerspaceMachineTypePolicy
    from apps.makerspaces.models import MakerspaceMembership, MakerspaceWaiver, MembershipPlan
    from apps.makerspaces.membership_plan_services import create_term
    from apps.makerspaces.waiver_services import accept_waiver, publish_waiver
    from apps.makerspaces.waiver_state import current_acceptance
    from apps.payments.models import MakerspacePaymentSettings
    from apps.presence.services import current_session, staff_check_in

    for key in ("machines", "machine_service", "membership", "presence"):
        install_module(makerspace, key, actor=actor)
    makerspace.refresh_from_db(fields=["enabled_modules", "enabled_features"])
    features = sorted((set(makerspace.enabled_features) | {
        "machines.job_requests", "machines.job_quotes", "charges.enabled", "charges.machines",
    }) - {"payments.machines", "charges.pricing", "charges.discounts", "billing.tax"})
    if makerspace.enabled_features != features:
        makerspace.enabled_features = features
        makerspace.save(update_fields=["enabled_features"])
        audit.record(actor, "makerspace.features_updated", makerspace=makerspace, target=makerspace,
                     meta={"enabled_features": features})
    kind, _ = MachineType.objects.get_or_create(makerspace=makerspace, slug="e2e-minute-service",
        defaults={"name": "E2E minute service", "is_builtin": False,
                  "capability_config": {"metering_unit": "minutes", "requires_booking": False}})
    queue, _ = ServiceQueue.objects.get_or_create(makerspace=makerspace, name="E2E minute service queue",
        defaults={"machine_type": kind, "is_active": True})
    machine, _ = Machine.objects.get_or_create(makerspace=makerspace, name="E2E minute service machine",
        defaults={"machine_type": kind, "is_active": True, "is_public": True, "open_to_all_members": True})
    MakerspaceMachineTypePolicy.objects.get_or_create(makerspace=makerspace, machine_type=kind,
        defaults={"accepts_job_requests": True, "quote_mode": "always", "payment_timing": "completion",
                  "file_groups": ["fab-3dprint"]})
    MakerspaceMachineTypePricing.objects.get_or_create(makerspace=makerspace, machine_type=kind,
        defaults={"payment_enabled": True, "rate_per_unit": "2.000", "flat_fee": "5.000"})
    payment_settings, _ = MakerspacePaymentSettings.objects.get_or_create(makerspace=makerspace)
    if payment_settings.default_currency != "usd":
        payment_settings.default_currency = "usd"
        payment_settings.save(update_fields=["default_currency"])
    membership = MakerspaceMembership.objects.get(makerspace=makerspace, user=member, status="active")
    waiver = MakerspaceWaiver.objects.filter(makerspace=makerspace, is_active=True).first()
    if waiver is None:
        waiver = publish_waiver(actor, makerspace, "E2E machine-service fixture waiver.", "e2e-machine-v1")
    if not current_acceptance(membership, active_waiver=waiver):
        membership, _ = accept_waiver(membership)
    plan, _ = MembershipPlan.objects.get_or_create(makerspace=makerspace, name="E2E machine member",
        defaults={"interval": "yearly", "amount": 0, "currency": "usd"})
    if not membership.terms.filter(status="active", starts_at__lte=timezone.now(), ends_at__gt=timezone.now()).exists():
        create_term(actor, membership, plan)
    if current_session(member, makerspace) is None:
        staff_check_in(actor, member, makerspace, 240, status="visiting")
    return {"queue_id": queue.pk, "machine_type_id": kind.pk, "machine_id": machine.pk}
