"""Hardware requests in every state, driven only through `hardware_requests.workflow`.

Issued and returned rows carry real evidence: a synthetic placeholder JPEG uploaded
to the private bucket's staging key (see `_showcase_evidence`), then consumed by the
workflow exactly as a staff upload would be. Box scans happen through `assign_box`
and `return_items`, so the Hard Rules (box QR scan + issue photo, return photo +
remark) are exercised rather than bypassed.
"""
from datetime import timedelta

from django.utils import timezone

from apps.hardware_requests import workflow
from apps.hardware_requests.request_workflow import RequesterSnapshot

from ._showcase_evidence import issue_photo, return_photo


class RequestSeeder:
    def __init__(self, makerspace, staff, members, stock):
        self.space = makerspace
        self.staff = staff
        self.members = members
        self.stock = stock
        self.photo_index = 0

    def run(self):
        s = self.staff
        self.submit("asha_menon", [("Arduino Uno R4", 2)], "Plant-watering sensor workshop")
        self.submit("ravi_kumar", [("Cordless Drill Kit", 1)], "Community garden bench build")
        accepted = self.submit("lena_ortiz", [("Multimeter", 1), ("Soldering Station", 1)],
                               "Repair cafe on Saturday")
        workflow.accept_request(s.inventory, accepted)
        rejected = self.submit("tomas_berg", [("Japanese Pull Saw", 1)], "Weekend joinery at home")
        workflow.reject_request(s.manager, rejected,
                                "Pull saws stay in the woodshop; book a bench session instead.")
        overdue = self.issue("meilin_chua", [("ESP32 Dev Board", 3)], "Mesh sensor network", 0)
        workflow.set_return_due(s.inventory, overdue, timezone.now() - timedelta(days=3))
        scope = self.stock.asset_payloads["Four-channel Oscilloscope"][:1]
        self.issue("kofi_mensah", [("Four-channel Oscilloscope", 1)], "Audio amplifier debugging", 1, scope)
        partial = self.issue("priya_nair", [("Digital Caliper", 3)], "Robotics club measuring day", 5)
        self.give_back(partial, [("Digital Caliper", 1, 0, 0)], "One caliper back early; two still out.")
        sewing = self.stock.asset_payloads["Sewing Machine"][:1]
        returned = self.issue("jonas_weber", [("Sewing Machine", 1)], "Costume repair evening", 6, sewing)
        self.give_back(returned, [("Sewing Machine", 1, 0, 0)], "Returned clean, bobbin case included.")
        issue = self.issue("sara_haddad", [("Precision Tweezers", 3)], "SMD soldering practice", 3)
        self.give_back(issue, [("Precision Tweezers", 1, 1, 1)],
                       "One pair bent at the tip, one pair not returned.")
        late = self.issue("diego_ramos", [("Wire Strippers", 1)], "Wiring a camper van", 2)
        workflow.set_return_due(s.inventory, late, timezone.now() + timedelta(days=5))

    def submit(self, username, lines, purpose):
        member = self.members[username]
        snapshot = RequesterSnapshot(
            username=member.username, name=member.display_name, email=member.email,
            phone="",
        )
        items = [{"product": self.stock.products[name], "quantity": qty} for name, qty in lines]
        return workflow.submit_request(
            self.space, items, purpose, requester_principal=member,
            contact_snapshot=snapshot, audit_actor=member,
        )

    def issue(self, username, lines, purpose, box_index, asset_payloads=None):
        request = self.submit(username, lines, purpose)
        request = workflow.accept_request(self.staff.inventory, request)
        desk = self.staff.desk
        request = workflow.assign_box(desk, request, self.stock.boxes[box_index].code)
        photo = issue_photo(self.space, desk, lines[0][0], self._next_photo())
        return workflow.issue_request(
            desk, request, photo.pk, "Checked condition with the member at the desk.",
            asset_qr_payloads=asset_payloads,
        )

    def give_back(self, request, outcomes, remark):
        desk = self.staff.desk
        items = {item.product.name: item for item in request.items.select_related("product")}
        resolutions = [
            {"item_id": items[name].pk, "returned": back, "damaged": damaged, "missing": missing}
            for name, back, damaged, missing in outcomes
        ]
        photo = return_photo(self.space, desk, outcomes[0][0], self._next_photo())
        return workflow.return_items(desk, request, photo.pk, remark,
                                     request.assigned_box.code, resolutions)

    def _next_photo(self):
        self.photo_index += 1
        return self.photo_index
