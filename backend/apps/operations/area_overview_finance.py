"""Finance grouped by area (decision 241, extends #100 and 217(c)).

Money in and out comes from `reports_finance_ledger.visible_rows`, the same rows the
income-versus-spending screen and reports read, already narrowed by `finance_scope`
(a Machine Manager to their machine types). "Owed" is the snapshot of charges still
pending today, narrowed the same way. Groups: area, then for inventory the lending vs
inventory split, for machines the machine type then the machine, for events the event.
No new authority: what a caller may see is exactly `finance_view(actor, space).sees`.
"""

from decimal import Decimal

from apps.operations.area_tree import GroupTree, none_key

#: Finance domains folded into one area (#100: the Inventory Manager owns both).
AREA_OF_DOMAIN = {"loans": "inventory", "inventory": "inventory"}
FINANCE_AREAS = ("inventory", "machines", "bookings", "events", "shop", "membership", "donations", "general")


def area_of(domain):
    return AREA_OF_DOMAIN.get(domain, domain)


def visible_areas(view):
    if view.everything:
        return list(FINANCE_AREAS)
    return [area for area in FINANCE_AREAS if any(area_of(domain) == area for domain in view.domains)]


def _machine_ids(pairs):
    """Machine id per (subject_type, subject_id) for machine jobs and machine sessions."""
    from apps.machines.models import MachineServiceRequest, MachineSession

    jobs = {sid for kind, sid in pairs if kind == "machine_service_request" and sid}
    sessions = {sid for kind, sid in pairs if kind == "machine_session" and sid}
    found = {}
    for pk, assigned, bucket in MachineServiceRequest.objects.filter(pk__in=jobs).values_list(
            "pk", "assigned_machine_id", "bucket__machine_id"):
        found[("machine_service_request", pk)] = assigned or bucket
    for pk, machine in MachineSession.objects.filter(pk__in=sessions).values_list("pk", "machine_id"):
        found[("machine_session", pk)] = machine
    return found


def _owed_rows(space, view):
    """Charges still pending now, as (domain, type, machine, event, currency, amount)."""
    from apps.payments.finance_rows import _event_ids, _machine_types, _session_types
    from apps.payments.finance_scope import PAYMENT_DOMAINS
    from apps.payments.models import Payment

    pending = list(Payment.objects.filter(makerspace=space, status=Payment.Status.PENDING).values_list(
        "subject_type", "subject_id", "currency", "amount"))
    pairs = [(kind, sid) for kind, sid, _currency, _amount in pending]
    jobs = _machine_types([sid for kind, sid in pairs if kind == "machine_service_request"])
    sessions = _session_types([sid for kind, sid in pairs if kind == "machine_session"])
    registrations = _event_ids([sid for kind, sid in pairs if kind == "event_registration"])
    from apps.events.orders_finance import subject_event_ids
    event_money = subject_event_ids(pairs)
    machines = _machine_ids(pairs)
    for kind, sid, currency, amount in pending:
        domain = PAYMENT_DOMAINS.get(kind, "general")
        type_id = jobs.get(sid) if kind == "machine_service_request" else (
            sessions.get(sid) if kind == "machine_session" else None)
        if not view.sees(domain, type_id):
            continue
        event_id = registrations.get(sid) if kind == "event_registration" else event_money.get((kind, sid))
        yield domain, type_id, machines.get((kind, sid)), event_id, currency.lower(), Decimal(amount)


def _names(type_ids, machine_ids, event_ids):
    from apps.events.models import Event
    from apps.machines.models import Machine, MachineType

    return (dict(MachineType.objects.filter(pk__in=type_ids).values_list("pk", "name")),
            dict(Machine.objects.filter(pk__in=machine_ids).values_list("pk", "name")),
            dict(Event.objects.filter(pk__in=event_ids).values_list("pk", "title")))


def _path(domain, type_id, machine_id, event_id, names):
    types, machines, events = names
    area = area_of(domain)
    path = [("area", f"area:{area}", area)]
    if area == "inventory":
        path.append(("domain", f"domain:{domain}", domain))
    elif domain == "machines":
        path.append(("machine_type", f"machine_type:{type_id}" if type_id else none_key("machine_type"),
                     types.get(type_id, "")))
        path.append(("machine", f"machine:{machine_id}" if machine_id else none_key("machine"),
                     machines.get(machine_id, "")))
    elif domain == "events":
        path.append(("event", f"event:{event_id}" if event_id else none_key("event"), events.get(event_id, "")))
    return path


def finance_tree(actor, space, view, *, date_range=None, areas=None):
    """The caller's finance, grouped. `areas` (a set) narrows to the chosen areas."""
    from apps.payments.reports_finance_ledger import visible_rows

    machine_pairs = []
    moved = []
    for row in visible_rows(space, date_range, actor):
        if areas and area_of(row.domain) not in areas:
            continue
        moved.append(row)
        if row.domain == "machines" and row.subject_id:
            machine_pairs.append((row.subject_type, row.subject_id))
    machines_of = _machine_ids(machine_pairs)
    owed = [row for row in _owed_rows(space, view) if not areas or area_of(row[0]) in areas]
    names = _names({row.machine_type_id for row in moved if row.machine_type_id} | {row[1] for row in owed if row[1]},
                   set(machines_of.values()) | {row[2] for row in owed if row[2]},
                   {row.event_id for row in moved if row.event_id} | {row[3] for row in owed if row[3]})
    tree = GroupTree()
    for row in moved:
        machine_id = machines_of.get((row.subject_type, row.subject_id)) if row.domain == "machines" else None
        tree.add(_path(row.domain, row.machine_type_id, machine_id, row.event_id, names), count=1,
                 finance={row.currency.lower(): {row.column: row.amount}})
    for domain, type_id, machine_id, event_id, currency, amount in owed:
        tree.add(_path(domain, type_id, machine_id, event_id, names), count=0, attention=1,
                 finance={currency: {"owed": amount}})
    return tree
