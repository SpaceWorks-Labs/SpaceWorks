"""Build report source facts through the machine-service workflow."""

from apps.machines import role_scope
from apps.machines.metering import metering_unit_for_pool
from apps.machines.service_workflow import accept, complete, fail, start, submit


def requester_for(space):
    """The space's fixture member account: service requests are submitted by members
    (account kinds) and processed by the separate staff ``actor``."""
    from apps.accounts.models import User
    from tests.accounts.account_factories import make_membership

    username = f"ab-service-requester-{space.pk}"
    user = User.objects.filter(username=username).first()
    if user is None:
        user = User.objects.create_user(username=username, email=f"{username}@example.test",
                                        access_status="active")
        make_membership(user, space)
    return user


def service(space, target, stock, actor, *, quantity=20, status="completed", consumptions=None, requester=None):
    if target.makerspace_id != space.pk:
        raise ValueError("Report fixture machine must belong to its makerspace.")
    if status not in {"completed", "failed", "in_progress"}:
        raise ValueError("Unsupported report fixture status.")
    reservation = {}
    actual = {}
    if stock is not None:
        if stock.unit == "grams":
            reservation = {"planned_grams": quantity}
            actual = {"actual_grams": quantity}
        else:
            kind = target.machine_type
            kind.capability_config = {**kind.capability_config, "metering_unit": metering_unit_for_pool(stock.unit)}
            kind.save(update_fields=["capability_config"])
            reservation = {"planned_quantity": quantity}
            actual = {"actual_quantity": quantity}
        reservation["consumable_pool_id"] = stock.pk
    requester = requester or requester_for(space)
    row = submit(target, requester, actor=requester, requester_name="", contact_email="", contact_phone="",
                 title="PRIVATE TITLE")
    accept(row, actor)
    row = start(row, actor, role_scope.EXEMPT, machine_id=target.pk, **reservation)
    if status == "in_progress":
        return row
    inputs = dict(actual_minutes=1, consumptions=consumptions or [], **actual)
    if status == "failed":
        return fail(row, actor, reason="Stopped partway", percent_complete=40, **inputs)
    return complete(row, actor, **inputs)
