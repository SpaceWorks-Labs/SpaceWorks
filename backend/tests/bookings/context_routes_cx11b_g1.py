"""Request/direct-handout context methods and both booking equipment pickers."""
from datetime import timedelta

from apps.bookings.models import Booking
from apps.bookings.models_loan_context import BookingLoanContext
from tests.bookings.route_support_cx11b_g1 import Route, equals, fields

REQUEST = ("bookings", "request_workflow", "loans.enabled")
DIRECT = (*REQUEST, "inventory.self_checkout")
ROUTES = tuple(Route(name, method, keys, audit=() if method == "GET" else ("loan.booking_context_changed",))
    for name, keys in (("admin-request-booking-context", REQUEST), ("admin-direct-loan-booking-context", DIRECT))
    for method in ("GET", "PUT", "DELETE")) + (
    Route("booking-equipment-request-products", keys=REQUEST),
    Route("booking-equipment-kits", keys=(*REQUEST, "inventory.consumables")),
)


def product(w, name, *, consumable=False):
    from apps.inventory.models import InventoryProduct
    return InventoryProduct.objects.create(makerspace=w.tenant, name=name, total_quantity=5, available_quantity=5,
        is_public=True, is_consumable=consumable)


def setup(w, monkeypatch):
    name, method = w.route.name, w.route.method
    tool = product(w, "G1 retained drill")
    if name.startswith("booking-equipment-"):
        return equipment(w, tool)
    from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem, PublicToolLoan
    req = HardwareRequest.objects.create(makerspace=w.tenant, requester=w.member,
        requester_username=w.member.username, status="pending_approval")
    HardwareRequestItem.objects.create(request=req, product=tool, requested_quantity=1)
    w.kwargs = {"makerspace_id": w.tenant.pk, "request_id": req.pk}
    if name == "admin-direct-loan-booking-context":
        # Existing handout projection; this test edits its optional context, never issues stock.
        loan = PublicToolLoan.objects.create(makerspace=w.tenant, request=req, requester=w.member,
            source="admin_direct", target_type="direct", target_id=req.pk, target_label=tool.name)
        w.kwargs = {"makerspace_id": w.tenant.pk, "loan_id": loan.pk}
    context = BookingLoanContext.objects.create(makerspace=w.tenant, request=req, booking=w.booking, active=True, revision=1)
    w.off["loans.enabled"] = (404, "module_disabled")
    if method == "GET":
        w.check = lambda r: equals((r.data["active"], r.data["revision"], r.data["booking_id"], r.data["can_write"]),
                                  (True, 1, w.booking.pk, True))
    else:
        w.body = {"expected_generation": w.tenant.loan_context_generations["bookings"], "expected_revision": 1}
        if method == "PUT":
            second = Booking.objects.create(space=w.room, member=w.member, name="Second G1 reservation", email=w.member.email,
                starts_at=w.start + timedelta(days=2), ends_at=w.start + timedelta(days=2, hours=1), status="confirmed")
            w.body["booking_id"] = second.pk
            def linked(r):
                fields(context, active=True, booking_id=second.pk, revision=2)
                equals(r.data["booking_id"], second.pk)
                fields(req, status="pending_approval")
                equals(BookingLoanContext.objects.filter(request=req).count(), 1)
            w.check = linked
        else:
            w.query_suffix = f"?intended_booking_id={w.booking.pk}"
            def unlinked(r):
                fields(context, active=False, booking_id=None, revision=2)
                equals((r.data["active"], r.data["revision"]), (False, 2))
                equals(Booking.objects.filter(pk=w.booking.pk).count(), 1)
            w.check = unlinked


def equipment(w, tool):
    w.kwargs = {"makerspace_id": w.tenant.pk, "space_id": w.room.pk}
    w.off["bookings"] = (404, "not_found")
    if w.route.name == "booking-equipment-request-products":
        w.off["loans.enabled"] = (404, "module_disabled")
        w.check = lambda r: equals(r.data["results"], [{"id": tool.pk, "name": tool.name, "event_only": False, "image_url": None}])
        return
    from apps.inventory.models_equipment_proposals import EquipmentKitTemplate, EquipmentKitVersion
    consumable = product(w, "G1 retained tape", consumable=True)
    templates = []
    for item, kind in ((tool, "returnable"), (consumable, "consumable")):
        template = EquipmentKitTemplate.objects.create(makerspace=w.tenant, name=item.name + " kit", published_for_contexts=True)
        EquipmentKitVersion.objects.create(template=template, version=1, name=template.name,
            lines=[{"product_id": item.pk, "quantity_per_person": 1, "kind": kind}])
        templates.append({"id": template.pk, "name": template.name, "version": 1,
            "lines": [{"product_id": item.pk, "display_name": item.name, "quantity_per_person": 1, "kind": kind}]})
    w.check = lambda r: equals(r.data["results"], templates)
    w.off.update({key: (200, None) for key in ("request_workflow", "loans.enabled", "inventory.consumables")})
    w.policy_off = lambda key, r: equals(r.data["results"], [templates[0] if key == "inventory.consumables" else templates[1]])
