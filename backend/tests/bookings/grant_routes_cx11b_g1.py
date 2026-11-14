"""Resource grants keep real MFA, native step-up, invitation binding and tenancy."""
from apps.bookings.models_staff_grants import BookingSpaceStaffGrant, BookingSpaceStaffGrantInvite
from apps.bookings.services_staff_grants import create_invite
from tests.bookings.route_support_cx11b_g1 import Route, equals, fields, person_client
from tests.modules.test_switch_matrix_objects_rest_additional_support import reauthenticate

KEYS = ("bookings", "bookings.staff_grants")
ROUTES = (
    Route("admin-accessible-booking-spaces", standing="discovery"),
    Route("admin-booking-staff-grants", keys=KEYS),
    Route("admin-booking-staff-invites", keys=KEYS),
    Route("admin-booking-staff-invites", "POST", KEYS, 201, ("booking.staff_grant_invited",)),
    Route("admin-booking-staff-grant-detail", "PATCH", KEYS, audit=("booking.staff_grant_updated",)),
    Route("admin-booking-staff-grant-revoke", "POST", KEYS, audit=("booking.staff_grant_revoked",)),
    Route("admin-booking-staff-invite-revoke", "POST", KEYS, audit=("booking.staff_grant_invite_revoked",)),
    Route("booking-staff-invite-redeem", "POST", KEYS,
        audit=("booking.staff_grant_created", "booking.staff_grant_invite_redeemed"), standing="invitation"),
)


def setup(w, monkeypatch):
    name, method = w.route.name, w.route.method
    if name == "admin-accessible-booking-spaces":
        w.kwargs = {}
        w.body = {"makerspace_id": w.tenant.pk}
        w.foreign_pair = (200, None)
        w.foreign_check = lambda r: equals(r.data["results"], [])
        w.off["bookings"] = (200, None)
        w.policy_off = lambda key, r: equals(r.data["results"], [])
        w.check = lambda r: equals([(x["id"], x["name"]) for x in r.data["results"]], [(w.room.pk, w.room.name)])
        return
    grant = BookingSpaceStaffGrant.objects.create(makerspace=w.tenant, space=w.room, user=w.member,
        permissions=["edit_details"], granted_by=w.actor)
    invite, secret = create_invite(w.room, actor=w.actor, permissions=["check_in"], email=w.member.email)
    if method != "GET" and w.native:
        reauthenticate(w.client, w.actor, password="G1-step-up-password-526!")
        reauthenticate(w.foreign, w.outsider, password="G1-step-up-password-526!")
    if name == "admin-booking-staff-grants":
        w.check = lambda r: equals([(x["id"], x["user"], x["permissions"]) for x in r.data["results"]],
            [(grant.pk, w.member.pk, ["edit_details"])])
    elif name == "admin-booking-staff-invites" and method == "GET":
        w.check = lambda r: equals([(x["id"], x["permissions"]) for x in r.data["results"]], [(invite.pk, ["check_in"])])
    elif name == "admin-booking-staff-invites":
        w.body = {"permissions": ["manage_reservations"], "email": w.member.email, "send_email": False}
        def invited(r):
            equals(BookingSpaceStaffGrantInvite.objects.filter(space=w.room).count(), 2)
            fields(BookingSpaceStaffGrantInvite.objects.get(pk=r.data["id"]), permissions=["manage_reservations"], created_by_id=w.actor.pk)
            assert len(r.data["token"]) >= 32
            equals(r["Cache-Control"], "private, no-store")
        w.check = invited
    elif name == "admin-booking-staff-grant-detail":
        w.kwargs = {"pk": grant.pk}
        w.body = {"permissions": ["check_in", "manage_reservations"]}
        w.check = lambda r: fields(grant, permissions=w.body["permissions"], revoked_at=None)
    elif name == "admin-booking-staff-grant-revoke":
        w.kwargs = {"pk": grant.pk}
        def revoked(r):
            grant.refresh_from_db()
            assert grant.revoked_at is not None
            equals(grant.revoked_by_id, w.actor.pk)
            equals(grant.permissions, ["edit_details"])
        w.check = revoked
    elif name == "admin-booking-staff-invite-revoke":
        w.kwargs = {"pk": invite.pk}
        def revoked(r):
            invite.refresh_from_db()
            assert invite.revoked_at is not None
            equals(invite.permissions, ["check_in"])
        w.check = revoked
    else:
        # Browser redemption admits a verified account without staff standing.
        # Native MEMBER redemption is forbidden by decision 173; exercise the
        # admitted existing STAFF device here, with its own verified-email invite.
        from apps.bookings.services_staff_grants import revoke_grant
        revoke_grant(grant, actor=w.actor)
        redeemer = w.actor if w.native else w.member
        if w.native:
            invite, secret = create_invite(w.room, actor=w.actor, permissions=["check_in"], email=redeemer.email)
        else:
            w.client = person_client(redeemer, w.tenant, False)
        w.kwargs, w.body = {}, {"token": secret}
        w.foreign_body = {"token": "invalid-token-" + "x" * 43}
        def redeemed(r):
            new = BookingSpaceStaffGrant.objects.get(space=w.room, user=redeemer, revoked_at__isnull=True)
            fields(new, permissions=["check_in"], granted_by_id=w.actor.pk)
            fields(invite, redeemed_by_id=redeemer.pk)
            assert invite.redeemed_at is not None
            equals(r.data["id"], new.pk)
            equals(BookingSpaceStaffGrant.objects.filter(space=w.room).count(), 2)
        w.check = redeemed
