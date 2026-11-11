"""Hand a damaged return line off to repairs, and read a loan's repair context back.

A return that records damage writes an immutable `RequesterAccountability` line with its
return photo (`return_helpers`). With `inventory.repairs` on, the area manager (Inventory
Manager or Space Manager) opens one repair issue for that line:

* source `loan`, linked to the loan and to the line itself (`IssueReport.return_line`,
  unique), subject the damaged unit when exactly one is known, else the item;
* it starts triaged with L12's work order, exactly like a staff-opened job;
* the return photo is referenced by id through the line, never copied into `IssuePhoto`;
* replaying the handoff answers the issue already opened (idempotent per line);
* it alerts staff like a reported issue and, when the repair is fixed or rejected, tells the
  borrower (`notify.loan_borrower_repair`); item managers and `accept_request` reviewers may hand off.

The return itself never waits on this: with repairs off there is simply no handoff, and
charges stay with `loan_charges_damage` (nothing here raises or reads money owed).
"""

from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.accounts import rbac
from apps.maintenance import work_orders

from . import areas, errors, history, notify

AREA = areas.INVENTORY


def is_manager(actor, space):
    return areas.manager_may(actor, space.pk, "inventory_product")


def require_manager(actor, space):
    """The item manager, or (dec 221c) a request reviewer who saw the damaged return."""
    areas.require(space, areas.REPAIRS[AREA])
    if not (is_manager(actor, space) or rbac.can(actor, rbac.Action.ACCEPT_REQUEST, space.pk)):
        raise errors.out_of_scope()


def damaged_lines(space, request_id):
    from apps.hardware_requests.models import RequesterAccountability
    return (RequesterAccountability.objects
            .filter(makerspace=space, request_id=request_id,
                    issue_type=RequesterAccountability.IssueType.DAMAGED)
            .select_related("request_item__product").order_by("pk"))


def return_remark(line):
    """The return's own remark (one `ReturnEvent` per return photo), else the line's note."""
    from apps.hardware_requests.models import ReturnEvent
    if line.evidence_photo_id:
        event = ReturnEvent.objects.filter(evidence_id=line.evidence_photo_id).only("remark").first()
        if event is not None and event.remark:
            return event.remark
    return line.description or ""


def damaged_asset(line):
    """The one damaged unit this line names, when the return identified exactly one."""
    from apps.hardware_requests.models import HardwareRequestItemAsset
    if line.quantity != 1 or not line.request_item_id or not line.evidence_photo_id:
        return None
    links = list(HardwareRequestItemAsset.objects.filter(
        request_item_id=line.request_item_id, outcome=HardwareRequestItemAsset.Outcome.DAMAGED,
        return_event__evidence_id=line.evidence_photo_id).select_related("asset")[:2])
    return links[0].asset if len(links) == 1 else None


def _subject(line):
    asset = damaged_asset(line)
    if asset is not None:
        return "inventory_asset", asset, {"asset": asset, "product": asset.product}
    product = line.request_item.product if line.request_item_id else None
    if product is None:
        raise errors.bad_state("This return line names no item to repair.", "return_line_no_item")
    return "inventory_product", product, {"product": product}


def hand_off(actor, space, accountability_id, *, note=""):
    """Open (or answer) the one repair issue for a damaged return line. Returns (issue, created)."""
    from apps.hardware_requests.models import RequesterAccountability
    from apps.maintenance.models import IssueReport
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    require_manager(actor, space)
    with transaction.atomic():
        assert_write_allowed(space.pk)
        line = get_object_or_404(
            RequesterAccountability.objects.select_for_update().filter(
                makerspace=space, issue_type=RequesterAccountability.IssueType.DAMAGED),
            pk=accountability_id)
        existing = IssueReport.objects.filter(return_line=line).first()
        if existing is not None:
            return existing, False
        subject_type, subject, fields = _subject(line)
        product = fields["product"]
        remark = return_remark(line)
        description = "\n".join(part for part in (
            f"Returned damaged on loan #{line.request_id} ({line.quantity} x {product.name}).",
            f"Return remark: {remark}" if remark else "", str(note or "").strip()) if part)
        issue = IssueReport.objects.create(
            makerspace=space, area=AREA, subject_type=subject_type, source=IssueReport.Source.LOAN,
            loan_id=line.request_id, return_line=line, title=f"Damaged on return: {product.name}"[:200],
            description=description[:4000], state=IssueReport.State.TRIAGED, **fields)
        issue.work_order = work_orders.create_work_order(
            actor, space, subject_type=subject_type, subject=subject, title=issue.title,
            description=issue.description, authorized=True)  # require_manager already admitted the actor
        issue.save(update_fields=["work_order", "updated_at"])
        history.step(issue, "triaged", actor, "repair.loan_handoff", note=note, meta={
            "request_id": line.request_id, "accountability_id": line.pk,
            "evidence_id": line.evidence_photo_id, "work_order_id": issue.work_order_id,
            "subject_type": subject_type, "by_reviewer": not is_manager(actor, space)})
        # Same staff notice and issue_reported webhook as a member's report (dec 221c); only on
        # first creation, so an idempotent replay never alerts twice. Fail-safe by `safe_adapter`.
        notify.staff(issue, "issue_reported")
    return issue, True
