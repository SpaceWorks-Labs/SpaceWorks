"""Small real objects and authenticated browser/native staff sessions for switch cases."""
import re
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection, transaction
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.views import APIView

from apps.accounts import mfa_policy
from apps.accounts.models import DeviceGrant
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.audit.models import AuditLog
from apps.bookings.models import BookableSpace
from apps.bookings.models_website import BookingResourcePage
from apps.boxes.models import Box
from apps.events.certificates.signatory_models import EventCertificateSignatory
from apps.events.models import EventAddon
from apps.events.models_website import EventPage
from apps.makerspaces.capabilities import FEATURES
from apps.machines.models import Machine, MachineType
from apps.operations.models import QrPrintBatch, StocktakeSession, StockTransfer
from apps.shop.models import ShopProduct, ShopVariant
from tests.accounts.account_factories import device_grant, make_staff
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.events.checkin_helpers import make_event
from tests.modules.switch_matrix_helpers import LIVE_FEATURES, MODULE_KEYS, dependents_closure, live_space
from tests.modules.switch_matrix_object_contracts import MODULES, OPERATIONS


def client_for(actor, space, native):
    row, _ = enrolled(actor)
    mfa_policy.stamp(actor, row)
    client = APIClient()
    if native:
        grant = device_grant(actor, staff_makerspace_id=space.pk)
        access, _refresh, _family = issue_device_token_pair(actor, grant)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}", HTTP_X_MAKERSPACE_ID=str(space.pk))
    else:
        force_recent_authenticate(client, actor, {"mfa_source": "verified", "mfa_version": str(row.version),
                                                "mfa_method": "totp"})
    return client


def object_world(native):
    space = live_space("sx-real-object", MODULE_KEYS)
    actor = make_staff(space, username="sx-real-object-manager", access_status="active")
    event = make_event(space)
    room = BookableSpace.objects.create(makerspace=space, name="Retained room", is_public=True)
    addon = EventAddon.objects.create(makerspace=space, event=event, name="Retained add-on", amount=0)
    signatory = EventCertificateSignatory.objects.create(event=event, slot=1, name="Retained signatory")
    machine_type = MachineType.objects.create(makerspace=space, slug="matrix-machine", name="Matrix machine type")
    machine = Machine.objects.create(makerspace=space, machine_type=machine_type, name="Retained machine")
    shop_product = ShopProduct.objects.create(makerspace=space, name="Retained shop product", slug="retained-product")
    shop_variant = ShopVariant.objects.create(makerspace=space, product=shop_product, name="Retained variant", price=0)
    objects = {
        "event": event, "addon": addon, "room": room, "signatory": signatory,
        "event_page": EventPage.objects.create(makerspace=space, event=event),
        "room_page": BookingResourcePage.objects.create(space=room),
        "machine": machine, "machine_type": machine_type, "shop_product": shop_product, "shop_variant": shop_variant,
        "box": Box.objects.create(makerspace=space, label="Retained shelf"),
        "stocktake": StocktakeSession.objects.create(makerspace=space, started_by=actor),
        "batch": QrPrintBatch.objects.create(makerspace=space, title="Retained labels", created_by=actor),
        "transfer": StockTransfer.objects.create(makerspace=space, source_makerspace=space,
                                                 destination_makerspace=space, reason="Retained transfer"),
    }
    return space, client_for(actor, space, native), objects


def retained(objects):
    result = {key: type(row)._base_manager.filter(pk=row.pk).values().get() for key, row in objects.items()}
    # Native authentication always advances last_used_at, including on a domain 404.
    # Authority, expiry, generation and every other grant value must remain identical.
    for row in DeviceGrant.objects.order_by("pk").values():
        row.pop("last_used_at")
        result[f"native-grant:{row['id']}"] = row
    return result


@contextmanager
def rolled_back():
    """Restore a probe inside Django's existing TestCase isolation transaction.

    A bare savepoint adds no application atomic block around the view. Preparation
    therefore runs before the view's own transactions, as it does in production.
    Never mark a harness atomic block as ``_from_testcase`` or patch a guard.
    """
    if connection.get_autocommit():
        # CX11B's transactional shards also import this public helper. Preserve
        # their existing isolation contract; their redesign belongs to that lane.
        with transaction.atomic():
            yield
            transaction.set_rollback(True)
        return
    assert connection.atomic_blocks and all(
        getattr(block, "_from_testcase", False) for block in connection.atomic_blocks
    ), "Object probes require Django TestCase isolation without a caller-held domain transaction"
    sid = transaction.savepoint()
    # Register the savepoint so nested on_commit callbacks carry its identity and
    # Django discards them on rollback, just as it discards the database writes.
    connection.savepoint_ids.append(sid)
    try:
        yield
    finally:
        assert connection.savepoint_ids.pop() == sid
        # A database error caught by a fail-safe view can leave this flag set.
        # Clear it only to roll back to the known-good probe boundary.
        transaction.set_rollback(False)
        transaction.savepoint_rollback(sid)
        transaction.savepoint_commit(sid)


def response_pair(response):
    data = getattr(response, "data", None)
    # Successful invitation/promo creation returns a secret called code, not an error.
    code = str(data["code"]) if response.status_code >= 400 and isinstance(data, dict) and "code" in data else None
    return response.status_code, code


def request(client, operation, objects):
    kwargs = {"pk": objects[operation.target].pk}
    if operation.name.endswith("signatory-detail"):
        kwargs["slot"] = 1
    cache.clear()
    body = dict(operation.body)
    return getattr(client, operation.method.lower())(reverse(operation.name, kwargs=kwargs), body, format="json")


def _no_write(execute, sql, params, many, context):
    assert not re.match(r"\s*(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE)\b", sql, re.I), sql.split(None, 1)[0]
    return execute(sql, params, many, context)


@contextmanager
def no_domain_writes():
    # Real native authentication must keep its heartbeat and device/channel activity.
    # Install the SQL guard immediately after authentication, before permissions,
    # throttles or handlers run; no domain mutation (including audit) is exempted.
    authenticate, dispatch = APIView.perform_authentication, APIView.dispatch
    def guarded_dispatch(view, *args, **kwargs):
        with ExitStack() as scope:
            def authenticated(instance, request):
                authenticate(instance, request)
                scope.enter_context(connection.execute_wrapper(_no_write))
            scope.enter_context(patch.object(APIView, "perform_authentication", authenticated))
            return dispatch(view, *args, **kwargs)
    # Response middleware also records channel activity, after the domain dispatch.
    with patch.object(APIView, "dispatch", guarded_dispatch):
        yield


def run_object_case(case):
    index, key, native = case
    operation = OPERATIONS[index]
    space, client, objects = object_world(native)
    before, audits = retained(objects), AuditLog.objects.count()
    # Roll back on-state commands too, so restoration can use the same object and body.
    with rolled_back():
        response = request(client, operation, objects)
        assert response_pair(response) == (operation.status, operation.code), (case, getattr(response, "data", None))

    feature = "." in key
    field = "enabled_features" if feature else "enabled_modules"
    original = list(getattr(space, field))
    off = {key} if feature else {key} | dependents_closure(key)
    if feature:
        while True:
            children = {name for name, definition in FEATURES.items() if set(definition.requires_features) & off}
            if children <= off:
                break
            off |= children
    setattr(space, field, sorted(set(original) - off))
    space.save(update_fields=[field])
    with no_domain_writes():
        response = request(client, operation, objects)
    code = operation.feature_code if feature else operation.module_code
    assert response_pair(response) == (404, code), (case, getattr(response, "data", None))
    if code in {"module_disabled", "feature_disabled"}:
        assert response.data["feature" if feature else "module"] == key
    assert retained(objects) == before
    assert AuditLog.objects.count() == audits

    setattr(space, field, original)
    space.save(update_fields=[field])
    assert retained(objects) == before
    with rolled_back():
        response = request(client, operation, objects)
        assert response_pair(response) == (operation.status, operation.code), (case, getattr(response, "data", None))
    assert retained(objects) == before
    assert AuditLog.objects.count() == audits


def validate_object_contracts():
    assert set(MODULES.values()) <= set(MODULE_KEYS)
    assert {operation.feature for operation in OPERATIONS if operation.feature} <= set(LIVE_FEATURES)
    assert len({(operation.name, operation.method) for operation in OPERATIONS}) == len(OPERATIONS)
