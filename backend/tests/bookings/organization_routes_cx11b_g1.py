"""Organization booking/hours methods and the intentionally inert member pool read."""
from datetime import timedelta

from apps.bookings.models import Booking
from apps.bookings.models_organization import BookingOrganizationLink
from apps.bookings.models_organization_hours import OrganizationHoursAllowance, OrganizationHoursLedger
from tests.bookings.route_support_cx11b_g1 import Route, equals, fields, window

KEYS = ("bookings", "bookings.organization_bookings")
ROUTES = (
    Route("admin-space-organization-booking", "POST", KEYS, 201, ("booking.organization_linked", "booking.created")),
    Route("admin-space-organization-booking-choices", keys=KEYS),
    Route("admin-org-hours-bank", keys=KEYS),
    Route("admin-org-hours-bank", "PATCH", KEYS, audit=("organization.hours_allowance_updated",)),
    Route("admin-org-hours-bank-ledger", keys=KEYS),
    Route("admin-org-hours-bank-ledger", "POST", KEYS, 201, ("organization.hours_adjusted",)),
    Route("admin-member-included-hours", keys=("bookings", "membership", "machines")),
)


def setup(w, monkeypatch):
    if w.route.name == "admin-member-included-hours":
        return member_hours(w)
    from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
    organization = Organization.objects.create(name="G1 retained partner", slug="g1-retained-partner")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=w.tenant, relationship="affiliate")
    OrganizationMembership.objects.create(organization=organization, user=w.member)
    name, method = w.route.name, w.route.method
    if name == "admin-space-organization-booking-choices":
        w.check = lambda r: equals(r.data, [{"organization_id": organization.pk, "name": organization.name,
            "contacts": [{"member_id": w.member.pk, "name": w.member.display_name or w.member.username}]}])
    elif name == "admin-space-organization-booking":
        w.body = {**window(w), "organization_id": organization.pk, "contact_member_id": w.member.pk}
        def booked(r):
            equals(Booking.objects.filter(space=w.room).count(), 2)
            fields(Booking.objects.get(pk=r.data["id"]), member_id=w.member.pk, starts_at=w.start + timedelta(days=1), status="confirmed")
            link = BookingOrganizationLink.objects.get(booking_id=r.data["id"])
            fields(link, organization_id=organization.pk, billed_member_id=w.member.pk, organization_name=organization.name)
        w.check = booked
    else:
        allowance = OrganizationHoursAllowance.objects.create(makerspace=w.tenant, organization=organization,
            allowance_minutes=120, period="none", updated_by=w.actor)
        ledger = OrganizationHoursLedger.objects.create(makerspace=w.tenant, organization=organization,
            entry="grant", minutes=30, period_key="all", reason="Retained top-up", actor=w.actor)
        w.kwargs = {"makerspace_id": w.tenant.pk, "organization_id": organization.pk}
        if name == "admin-org-hours-bank" and method == "GET":
            w.check = lambda r: equals((r.data["organization_id"], r.data["allowance_minutes"], r.data["remaining_minutes"]),
                                       (organization.pk, 120, 150))
        elif name == "admin-org-hours-bank":
            w.body = {"allowance_minutes": 240, "period": "none"}
            def updated(r):
                fields(allowance, allowance_minutes=240, period="none", updated_by_id=w.actor.pk)
                equals(r.data["remaining_minutes"], 270)
                equals(OrganizationHoursLedger.objects.filter(organization=organization).count(), 1)
            w.check = updated
        elif method == "GET":
            w.check = lambda r: equals([(x["id"], x["minutes"], x["reason"]) for x in r.data["results"]],
                                       [(ledger.pk, 30, "Retained top-up")])
        else:
            w.body = {"entry": "adjust", "minutes": -15, "reason": "G1 adjustment Δ"}
            def adjusted(r):
                equals(OrganizationHoursLedger.objects.filter(organization=organization).count(), 2)
                fields(OrganizationHoursLedger.objects.get(pk=r.data["id"]), entry="adjust", minutes=-15,
                    reason=w.body["reason"], actor_id=w.actor.pk, period_key="all")
                fields(ledger, minutes=30, reason="Retained top-up")
            w.check = adjusted


def member_hours(w):
    from tests.payments.pricing.helpers import plan, put_on_plan
    pro = plan(w.tenant, name="G1 included plan")
    pro.included_booking_hours, pro.included_machine_hours = 3, 2
    pro.save(update_fields=["included_booking_hours", "included_machine_hours"])
    term = put_on_plan(w.tenant, w.member, pro)
    w.kwargs = {"makerspace_id": w.tenant.pk, "user_id": w.member.pk}
    def pools(r):
        equals((r.data["member_id"], r.data["enabled"]), (w.member.pk, True))
        equals([(x["kind"], x["term_id"], x["plan_name"], x["allowance_minutes"], x["used_minutes"], x["remaining_minutes"])
            for x in r.data["pools"]], [("booking", term.pk, pro.name, 180, 0, 180), ("machine", term.pk, pro.name, 120, 0, 120)])
    w.check = pools
    w.off = {key: (200, None) for key in w.route.keys}
    def inert(key, r):
        if key == "machines":
            equals([(x["kind"], x["remaining_minutes"]) for x in r.data["pools"]], [("booking", 180)])
            equals(r.data["enabled"], True)
        else:
            equals(r.data, {"member_id": w.member.pk, "enabled": False, "pools": []})
    w.policy_off = inert
