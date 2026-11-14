"""Build real /control/ forms without bypassing model validation or permissions."""
from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from apps.apiclients.models import ApiClient
from apps.boxes.models import Box
from apps.integrations.models_destinations import NotificationDestination
from apps.inventory.models import InventoryAsset, InventoryProduct
from apps.machines.models import Machine, MachineType
from apps.operations.models import StocktakeSession


def row_for(key, space, label):
    if key == "products":
        return InventoryProduct(makerspace=space, name=label)
    if key == "assets":
        product = InventoryProduct.objects.get(makerspace=space, name="Asset parent")
        return InventoryAsset(makerspace=space, product=product, asset_tag=label)
    if key == "machines":
        machine_type = MachineType.objects.get(makerspace=space, slug="quota-type")
        return Machine(makerspace=space, machine_type=machine_type, name=label)
    if key == "api_clients":
        return ApiClient(makerspace=space, label=label, allowed_origins=["https://example.test"])
    if key == "boxes":
        return Box(makerspace=space, label=label)
    if key == "webhook_endpoints":
        row = NotificationDestination(makerspace=space, label=label, channel="webhook")
        row.set_webhook_url("https://example.test/hook")
        return row
    if key == "stocktake_sessions_monthly":
        return StocktakeSession(makerspace=space, notes=label)
    raise AssertionError(key)


def prepare(key, space):
    if key == "assets":
        InventoryProduct.objects.create(makerspace=space, name="Asset parent", tracking_mode="individual")
    if key == "machines":
        MachineType.objects.create(makerspace=space, slug="quota-type", name="Quota type")


def bound_form(row, actor, *, instance=None):
    if isinstance(row, StocktakeSession) and row.started_by_id is None:
        row.started_by = actor
    model_admin = admin.site._registry[type(row)]
    request = RequestFactory().post("/control/")
    request.user = actor
    request.session = {}
    request._messages = FallbackStorage(request)
    form_class = model_admin.get_form(request, obj=instance)
    initial = form_class(instance=row)
    data = {name: field.value() for name, field in initial._bound_items() if field.value() is not None}
    if isinstance(row, NotificationDestination):
        # No DNS request: the write-only field is blank and the existing encrypted
        # credential is retained, as on a normal edit of a configured endpoint.
        data["new_webhook_url"] = ""
    return form_class(data=data, instance=instance or row), model_admin, request, data


def form_errors(form):
    return [(error.code, error.message) for error in form.non_field_errors().as_data()]
