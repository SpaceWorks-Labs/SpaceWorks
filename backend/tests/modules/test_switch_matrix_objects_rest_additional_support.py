"""Small folded-capability, campaign, pass and supervised-session objects."""
from datetime import timedelta

from django.utils import timezone
from django.core.cache import cache

from tests.accounts.account_factories import grant_staff_role
from tests.modules.switch_matrix_object_helpers import client_for

PASSWORD = "CX11B real native reauthentication 507!"


def reauthenticate(client, actor, *, password=PASSWORD):
    from apps.accounts.mfa_crypto import totp
    from apps.accounts.models_mfa import UserMFA
    from apps.makerspaces.secrets import decrypt_value
    row = UserMFA.objects.get(user=actor, enabled_at__isnull=False)
    now = timezone.now()
    current = int(now.timestamp() // 30)
    # The verifier admits the adjacent counter for clock skew. Use it for a
    # second step-up without resetting MFA or stamping a future auth_time.
    step = max(current, row.last_step + 1)
    assert step <= current + 1, "Advance the fixture clock before another step-up."
    code = totp(decrypt_value(row.secret), step)
    response = client.post("/api/v1/auth/reauth", {"password": password, "code": code}, format="json")
    assert (response.status_code, response.data.get("code")) == (200, None), response.data
    assert response.data == {"verified": True, "expires_in": 600}
    row.refresh_from_db()
    assert row.last_step == step


def additional(op, space, client, objects, actor, member, body, native):
    now, room, machine = timezone.now(), objects["room"], objects["machine"]
    if op.name == "machine-type-intake":
        kind = objects["machine_type"]
        kind.intake_schema = {"version": 1, "fields": [{"key": "purpose", "label": "Retained purpose",
            "type": "text", "required": True}]}
        kind.save(update_fields=["intake_schema"])
    if op.name == "admin-machine-job-consumables":
        from apps.machines.models_consumable_profiles import MachineTypeConsumable
        objects["profile"] = MachineTypeConsumable.objects.create(makerspace=space,
            machine_type=objects["machine_type"], key="paper", name="Retained paper", unit="sheet",
            record_by=["staff"], estimate_by="staff", required=True)
    if op.name == "admin-machine-job-reorder":
        from apps.machines import service_workflow as workflow
        job, queue = objects["job"], objects["queue"]
        peer = workflow.submit(queue, member, member=member, actor=actor, requester_name="Retained borrower",
            contact_email=member.email, contact_phone="", title="Earlier waiting peer")
        peer = workflow.accept(peer, actor, estimated_minutes=10)
        type(job).objects.filter(pk=peer.pk).update(queued_at=now - timedelta(hours=1))
        type(job).objects.filter(pk=job.pk).update(queued_at=now)
        peer.refresh_from_db()
        job.refresh_from_db()
        objects["second_job"] = peer
    if op.name in {"admin-bookable-space-photos", "admin-bookable-space-photo-order"}:
        from apps.bookings.models_gallery import BookableSpacePhoto
        for index, key in enumerate(("photo_one", "photo_two"), 1):
            objects[key] = BookableSpacePhoto.objects.create(space=room, object_key=f"gallery/{room.pk}/{index}.png",
                size_bytes=10, caption=f"Retained photo {index}", position=index, uploaded_by=actor)
        if op.method == "PUT":
            body = {"order": [objects["photo_two"].pk, objects["photo_one"].pk]}
    if op.name == "admin-booking-pass-template" and op.method == "PUT":
        from copy import deepcopy
        from apps.bookings.pass_templates import DEFAULT_PASS_TEMPLATE
        body = deepcopy(DEFAULT_PASS_TEMPLATE)
        body["orientation"] = "landscape"
    if op.seed == "owner_booking":
        grant_staff_role(member, space)
        client = client_for(member, space, native)
    if op.seed == "recurring":
        body = {"member_id": member.pk, "count": 2, "starts_at": (now + timedelta(days=7)).isoformat(),
                "ends_at": (now + timedelta(days=7, hours=1)).isoformat()}
    if op.seed == "broadcast":
        from apps.bookings.services_broadcasts import compose
        values = {"subject": "Workshop arrangements", "body": "Please arrive at the front desk.",
                  "window_start": now + timedelta(days=1), "window_end": now + timedelta(days=4), "statuses": ["confirmed"]}
        objects["campaign"] = compose(room, actor, **values)
        if op.name == "admin-booking-broadcasts" and op.method == "POST":
            body = {**values, "window_start": values["window_start"].isoformat(), "window_end": values["window_end"].isoformat()}
    if op.seed in {"supervised", "supervised_use"}:
        from apps.machines.models import SupervisedSession, SupervisedParticipant, SupervisedUse
        session = SupervisedSession.objects.create(makerspace=space, machine=machine, instructor=actor,
            event=objects["event"], opened_at=now - timedelta(minutes=10), note="Retained workshop")
        objects["supervised"] = session
        objects["participant"] = SupervisedParticipant.objects.create(session=session, user=member, added_by=actor,
            added_at=now - timedelta(minutes=5))
        if op.name == "member-supervised-people":
            from tests.rbac_f6_helpers import community_member
            from apps.events.models import EventRegistration
            candidate = community_member(space, "cx11b-picker-candidate").user
            candidate.display_name = "Picker candidate"
            candidate.save(update_fields=["display_name"])
            EventRegistration.objects.create(event=objects["event"], member=candidate,
                name=candidate.display_name, email=candidate.email, status="registered")
            objects["candidate"] = candidate
            body = {"q": "Picker"}
        if op.name == "member-supervised-use-start":
            body["user_id"] = member.pk
        if op.seed == "supervised_use":
            objects["use"] = SupervisedUse.objects.create(session=session, user=member, instructor=actor,
                started_at=now - timedelta(minutes=2))
    if op.seed == "schedule":
        from apps.maintenance.models import MaintenanceSchedule
        objects["schedule"] = MaintenanceSchedule.objects.create(machine=machine, description="Retained inspection",
            interval_days=30, next_due=(now + timedelta(days=30)).date(), created_by=actor)
    if op.seed == "warranty":
        from apps.warranty.models import Warranty
        objects["warranty"] = Warranty.objects.create(makerspace=space, machine=machine, vendor_name="Retained warranty supplier")
    if op.seed == "vendor":
        from apps.procurement.models import Vendor
        objects["vendor"] = Vendor.objects.create(makerspace=space, name="Retained vendor", created_by=actor)
    if op.seed in {"tobuy", "machine_tobuy"}:
        from apps.procurement.models import ToBuyItem
        objects[op.target] = ToBuyItem.objects.create(makerspace=space, name="Retained procurement item",
            kind="printing" if op.seed == "machine_tobuy" else "hardware", quantity=2,
            **({"machine_type": objects["machine_type"]} if op.seed == "machine_tobuy" else {}))
    if op.seed == "incident":
        from apps.maintenance.incidents.models import Incident, IncidentAction
        row = Incident.objects.create(makerspace=space, title="Retained safety report", reporter=actor, area="other")
        objects["incident"] = row
        objects["incident_action"] = IncidentAction.objects.create(incident=row, description="Retained follow-up")
    if op.seed == "organization":
        from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
        org = Organization.objects.create(name="Retained partner", slug="cx11b-partner")
        objects["organization"] = org
        objects["organization_link"] = OrganizationMakerspace.objects.create(organization=org, makerspace=space, relationship="affiliate")
        objects["organization_member"] = OrganizationMembership.objects.create(organization=org, user=member)
        if op.method == "POST":
            body = {"organization_id": org.pk, "contact_member_id": member.pk,
                "starts_at": (now + timedelta(days=7)).isoformat(), "ends_at": (now + timedelta(days=7, hours=1)).isoformat()}
    if op.seed == "staff_grant":
        from apps.bookings.models_staff_grants import BookingSpaceStaffGrant
        from apps.bookings.services_staff_grants import create_invite
        objects["booking_grant"] = BookingSpaceStaffGrant.objects.create(makerspace=space, space=room, user=member,
            permissions=["edit_details"], granted_by=actor)
        objects["booking_invite"], _secret = create_invite(room, actor=actor, permissions=["check_in"])
        if native:
            actor.set_password(PASSWORD)
            actor.save(update_fields=["password"])
            client = client_for(actor, space, native)
            reauthenticate(client, actor)
    return client, body


def send(client, operation, url, body):
    cache.clear()
    headers = {"HTTP_IDEMPOTENCY_KEY": str(body["operation_id"])} if "operation_id" in body else {}
    return getattr(client, operation.method.lower())(url, body, format="json", **headers)

