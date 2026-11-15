"""Closed URL/service inventory and AST ordering; one resolver crawl per module."""

import ast
from copy import deepcopy
from functools import lru_cache

import pytest
from django.urls import URLResolver, get_resolver

from tests.payments.fundraising_structure_cx14 import (
    CONTEXT, FENCE, NOTICE_WRAPPER, PACKAGE, dotted, inventory, resolve, service_entries, violations,
)

pytestmark = pytest.mark.area_payments
ROUTES = {
    "public-donation-page": "get", "public-donations": "post", "public-donation-email-code": "post",
    "public-donation-pledges": "post", "public-sponsor-wall": "get", "public-event-sponsors": "get",
    "public-donation-status": "get", "public-donation-checkout": "post", "public-donation-claim": "post",
    "public-donation-tax-receipt": "get", "public-pledge-manage": "get post",
    "admin-donations": "get post", "admin-donation-settings": "get put",
    "admin-donation-campaigns": "get post", "admin-donation-campaign": "patch",
    "admin-donation-pledges": "get", "admin-donation-pledge": "post", "admin-donation-cancel": "post",
    "admin-donation-return": "post", "admin-donation-tax-receipt": "get", "admin-donation-donors": "get",
    "admin-donation-export": "get", "admin-donation-receipt-reissue": "post",
    "admin-donation-claim-confirm": "post", "admin-donation-claim-reject": "post",
    "admin-sponsors": "get post", "admin-sponsor-tiers": "get post", "admin-sponsor-tier": "patch",
    "admin-sponsor-perks": "get post", "admin-sponsor-perk-fulfil": "post", "admin-sponsor-charge-return": "post",
    "admin-sponsor-event-link": "delete", "admin-sponsor-event-sponsors": "get", "admin-sponsor": "get patch",
    "admin-sponsor-archive": "post", "admin-sponsor-restore": "post", "admin-sponsor-logo": "post put delete",
    "admin-sponsor-charges": "get post", "admin-sponsor-event-links": "get post",
    "member-donations": "get", "member-donation-tax-receipt": "get", "member-pledges": "get",
    "member-pledge": "post",
}
SERVICES = {
    "identity.donor_for", "identity.send_code", "services.create_gift", "services.tax_detail_for",
    "services.checkout_url", "services.record_desk_gift", "services.cancel_gift",
    "pledges.create_pledge", "pledges.change_pledge", "pledges.raise_period", "pledges.raise_one",
    "sponsors.save_sponsor", "sponsors.archive_sponsor", "sponsors.copy_tier_perks", "sponsors.save_perk",
    "sponsors.fulfil_perk", "sponsors.raise_charge", "sponsors.link_event_sponsor", "sponsors.unlink_event_sponsor",
    "tasks.raise_pledges_task", "tasks.remind_perk", "tasks.remind_perks_task", "tax_receipts.freeze",
    "refunds.open_return_case", "notices.notify_receipt", "notices.notify_pledge_due", "notices.notify_perk_due",
    "settlement.after_settlement", "settlement.after_settlement.resume", "settlement.mark_gift",
    "settlement.mark_sponsorship",
}


@lru_cache(maxsize=1)
def url_entries():
    found = {}

    def walk(patterns):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                walk(pattern.url_patterns)
                continue
            cls = getattr(pattern.callback, "cls", None)
            if cls is None or not cls.__module__.startswith(PACKAGE + "."):
                continue
            for method in ("get", "post", "put", "patch", "delete"):
                if hasattr(cls, method):
                    handler = getattr(cls, method)
                    entry = handler.__module__ + "." + handler.__qualname__
                    key = pattern.name, method
                    assert key not in found or found[key] == entry, (key, found.get(key), entry)
                    found[key] = entry
    walk(get_resolver().url_patterns)
    return found


def test_no_unreviewed_fundraising_route_or_service_entry():
    assert set(url_entries()) == {(name, method) for name, methods in ROUTES.items() for method in methods.split()}
    assert service_entries() == {PACKAGE + "." + name for name in SERVICES}


def test_every_resolved_handler_and_service_fences_before_effects():
    entries = set(url_entries().values()) | service_entries()
    failures = {entry: errors for entry in sorted(entries) if (errors := violations(entry))}
    assert failures == {}


@pytest.mark.parametrize("entry,requirements", [
    ("views_public._locked_donor", {"money": "True", "tax_request": "data"}),
    ("identity.donor_for", {"money": "True", "tax_request": "data"}),
    ("views_staff.DonationListView.post", {"money": "True", "tax": "tax"}),
    ("services.create_gift", {"money": "True", "tax": "tax if source != Donation.Source.PLEDGE or tax_detail is None else None"}),
    ("services.record_desk_gift", {"money": "True", "tax": "tax"}),
    ("services.tax_detail_for", {"money": "True", "tax": "(True, pan, address)"}),
    ("pledges.create_pledge", {"money": "True", "tax": "tax"}),
    ("pledges.raise_period", {"money": "True"}), ("sponsors.raise_charge", {"money": "True"}),
    ("views_guest.GuestGiftClaimView.post", {"features": "('billing.offline_claims',)"}),
    ("views_staff_area.GiftClaimDecisionView.post", {"features": "('billing.offline_claims',)"}),
])
def test_conditional_switch_requirements_are_present_at_own_boundary(entry, requirements):
    functions, imports = inventory()
    name = PACKAGE + "." + entry
    calls = [node for node in ast.walk(functions[name][1]) if isinstance(node, ast.Call)
             and resolve(name, dotted(node.func), functions, imports) in {FENCE, CONTEXT}]
    assert any(all({kw.arg: ast.unparse(kw.value) for kw in call.keywords}.get(key) == value
                   for key, value in requirements.items()) for call in calls)


def test_fence_locks_fresh_before_all_checks_and_yields_that_row():
    functions, _ = inventory()
    node = functions[FENCE][1]
    source = ast.unparse(node)
    assert "space = require_feature_locked(space, DONATIONS)" in source
    assert "if not feature_enabled(space, key):\n            raise feature_off(key)" in source
    assert "if not feature_enabled(space, feature):\n            raise feature_off(feature)" in source
    assert "if money:\n        require_tracking(space)" in source
    assert "if tax_request is not None or (tax and tax[0]):" in source
    assert "clean_request(space," in source
    assert "yield require_fundraising_locked(makerspace_id, key, **requirements)" in ast.unparse(functions[CONTEXT][1])


def test_only_reviewed_core_paths_may_bypass_fundraising_admission():
    functions, imports = inventory()
    bypasses = set()
    for name, (_module, node) in functions.items():
        for call in ast.walk(node):
            if not isinstance(call, ast.Call) or resolve(name, dotted(call.func), functions, imports) not in {FENCE, CONTEXT}:
                continue
            for keyword in call.keywords:
                if keyword.arg == "key" and any(isinstance(child, ast.Constant) and child.value is None
                                                for child in ast.walk(keyword.value)):
                    bypasses.add((name.removeprefix(PACKAGE + "."), ast.unparse(keyword.value)))
    # after_settlement contains the callback body, which has no gate of its own.
    assert bypasses == {
        ("services.checkout_url", "None"), ("tax_receipts.freeze", "None"),
        ("settlement.mark_gift", "None"), ("settlement.mark_sponsorship", "None"),
        ("notices._send", "None if event == 'donation_received' else PLEDGES"),
    }
    for entry, predicate, write in (
        ("services.checkout_url", "online_payments_enabled", "create_checkout_url"),
        ("tax_receipts.freeze", "receipts_available", "save"),
    ):
        node = functions[PACKAGE + "." + entry][1]
        calls = [call for call in ast.walk(node) if isinstance(call, ast.Call)]
        before = min(call.lineno for call in calls if dotted(call.func).split(".")[-1] == predicate)
        after = min(call.lineno for call in calls if dotted(call.func).split(".")[-1] == write)
        assert before < after
        branch = next(child for child in ast.walk(node) if isinstance(child, ast.If)
                      and any(isinstance(call, ast.Call) and dotted(call.func).split(".")[-1] == predicate
                              for call in ast.walk(child.test)))
        assert any(isinstance(child, ast.Return) for child in branch.body)


@pytest.mark.parametrize("entry,key", [
    ("pledges.create_pledge", "PLEDGES"), ("pledges.change_pledge", "PLEDGES"),
    ("pledges.raise_period", "PLEDGES"),
    *[("sponsors." + name, "SPONSORS") for name in (
        "save_sponsor", "archive_sponsor", "copy_tier_perks", "save_perk", "fulfil_perk", "raise_charge",
        "link_event_sponsor", "unlink_event_sponsor")],
    *[("views_sponsor_logo.SponsorLogoView." + method, "SPONSORS") for method in ("post", "put", "delete")],
    ("views_sponsors.TierListView.post", "SPONSORS"), ("views_sponsors.TierDetailView.patch", "SPONSORS"),
    ("tasks.remind_perk", "SPONSORS"),
])
def test_child_switch_is_part_of_the_shared_fence(entry, key):
    functions, imports = inventory()
    name = PACKAGE + "." + entry
    calls = [node for node in ast.walk(functions[name][1]) if isinstance(node, ast.Call)
             and resolve(name, dotted(node.func), functions, imports) in {FENCE, CONTEXT}]
    assert any((len(call.args) > 1 and ast.unparse(call.args[1]) == key)
               or any(kw.arg == "key" and ast.unparse(kw.value) == key for kw in call.keywords) for call in calls)


@pytest.mark.parametrize("body", [
    "row.save()\nrequire_fundraising_locked(space)",
    "rows.update(reminded_on=today)\nrequire_fundraising_locked(space)",
    "if enabled:\n    require_fundraising_locked(space)\nrow.save()",
    "enabled and require_fundraising_locked(space)\nrow.save()",
    "with donation_write(space):\n    pass\nrow.save()",
    "require_fundraising_locked(get_or_create_anonymous_requester(space))",
    "with donation_write(space, tax=consume_code(space, email, code)):\n    pass",
    "consume_alias(space, email, code)\nrequire_fundraising_locked(space)",
])
def test_guard_rejects_late_branch_escaped_and_argument_side_effects(body):
    name = PACKAGE + ".synthetic.operation"
    node = ast.parse("def operation():\n" + "\n".join("    " + line for line in body.splitlines())).body[0]
    functions = {name: (PACKAGE + ".synthetic", node)}
    imports = {PACKAGE + ".synthetic": {"require_fundraising_locked": FENCE, "donation_write": CONTEXT,
        "consume_alias": "apps.hardware_requests.contact_verification.consume_code"}}
    assert violations(name, functions, imports), body


@pytest.mark.parametrize("assigned", [
    "Donation.objects.create", "consume_code", "fanout", "_write", "getattr(Donation.objects, 'create')",
])
@pytest.mark.parametrize("fenced", [False, True])
def test_assigned_callables_are_discovered_and_have_exact_ordering_violations(assigned, fenced):
    functions, imports = inventory()
    functions, imports = dict(functions), dict(imports)
    module, name = PACKAGE + ".synthetic", PACKAGE + ".synthetic.new_entry"
    gate = "    require_fundraising_locked(space)\n" if fenced else ""
    source = ("def new_entry(space):\n" + gate + f"    write = {assigned}\n"
              "    return write(makerspace=space)\n\ndef _write(**kwargs):\n    row.save()\n")
    entry, helper = ast.parse(source).body
    functions.update({name: (module, entry), module + "._write": (module, helper)})
    imports[module] = {"require_fundraising_locked": FENCE,
                       "consume_code": "apps.hardware_requests.contact_verification.consume_code",
                       "fanout": "apps.operations.notifications_p2.fanout"}
    # Plant the public entry into the real inventory; the original exact set
    # would now FAIL, rather than silently missing the assigned callable.
    assert service_entries(functions, imports) == service_entries() | {name}
    if fenced:
        expected = []
    elif assigned == "_write":
        expected = [(module + "._write", 6, "row.save")]
    else:
        expected = [(name, 3, "write")]
    assert violations(name, functions, imports) == expected


@pytest.mark.parametrize("binding", [
    "write: object = Donation.objects.create",
    "alias = Donation.objects.create\nwrite = alias",
    "write = alias = Donation.objects.create",
    "write, unused = Donation.objects.create, None",
    "write = Donation.objects.create if enabled else harmless",
])
def test_callable_assignment_forms_resolve_or_fail_closed(binding):
    module, name = PACKAGE + ".synthetic", PACKAGE + ".synthetic.new_entry"
    source = "def new_entry(space):\n" + "\n".join("    " + line for line in binding.splitlines())
    node = ast.parse(source + "\n    return write(makerspace=space)\n").body[0]
    functions, imports = {name: (module, node)}, {module: {}}
    assert service_entries(functions, imports) == {name}
    assert violations(name, functions, imports) == [(name, node.body[-1].lineno, "write")]


@pytest.mark.parametrize("entry,key", [("notify_pledge_due", "PLEDGES"), ("notify_perk_due", "SPONSORS")])
def test_deferred_dispatch_fence_is_outside_safe_wrapper_and_worker_rechecks(entry, key):
    functions, imports = inventory()
    name = PACKAGE + ".notices." + entry
    node = functions[name][1]
    decorators = [ast.unparse(item) for item in node.decorator_list]
    subject = entry.removeprefix("notify_").removesuffix("_due")
    assert decorators[0] == f"_fundraising_notification({key}, subject='{subject}')"
    assert decorators[1:] == ["safe_notification", "transaction.atomic"]
    assert f"require_fundraising_locked({subject}.makerspace_id, {key})" in ast.unparse(node)
    wrapper = functions[NOTICE_WRAPPER][1]
    assert "with transaction.atomic():\n            require_fundraising_locked(row.makerspace_id, key)" in ast.unparse(wrapper)
    assert violations(name, functions, imports) == []
    # Leave the registered body's fence intact, but move admission behind the
    # dispatcher: the structural proof must still reject the public entry.
    broken = deepcopy(functions)
    atomic = next(child for child in ast.walk(broken[NOTICE_WRAPPER][1]) if isinstance(child, ast.With))
    gate = atomic.body.pop(0)
    atomic.body.append(gate)
    call = next(child for child in ast.walk(atomic) if isinstance(child, ast.Call) and dotted(child.func) == "function")
    assert violations(name, broken, imports) == [(NOTICE_WRAPPER, call.lineno, "function")]
    reordered = deepcopy(functions)
    decorated = reordered[name][1]
    decorated.decorator_list[:2] = decorated.decorator_list[1::-1]
    assert violations(name, reordered, imports) == [(name, node.lineno, "safe_notification")]
