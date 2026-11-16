"""Absent admin creators are proved by their real permission and HTTP refusal."""
import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse

from apps.bookings.models import BookableSpace, Booking
from apps.card_designs.models_staff_cards import StaffCard
from apps.data_export.models import DataExportJob
from apps.devices.models import Device
from apps.events.models import Event, EventRegistration, EventSeries
from apps.integrations.models import DailyEmailCounter, DailyNotificationCounter
from apps.machines.models import MachineServiceRequest
from apps.makerspaces.models import MakerspaceMembership, MemberCard, MembershipPlan
from apps.shop.models import ShopOrder, ShopProduct
from tests.accounts.reauth_helpers import force_recent_control_login
from tests.r2_superadmin_local.helpers import superadmin

pytestmark = pytest.mark.django_db
CASES = [
    pytest.param(Event, marks=pytest.mark.area_events),
    pytest.param(EventSeries, marks=pytest.mark.area_events),
    pytest.param(EventRegistration, marks=pytest.mark.area_events),
    pytest.param(BookableSpace, marks=pytest.mark.area_bookings),
    pytest.param(Booking, marks=pytest.mark.area_bookings),
    pytest.param(MakerspaceMembership, marks=pytest.mark.area_membership),
    pytest.param(MembershipPlan, marks=pytest.mark.area_membership),
    pytest.param(MemberCard, marks=pytest.mark.area_membership),
    pytest.param(StaffCard, marks=pytest.mark.area_membership),
    pytest.param(Device, marks=pytest.mark.area_devices),
    pytest.param(MachineServiceRequest, marks=pytest.mark.area_machine_service),
    pytest.param(ShopProduct, marks=pytest.mark.area_shop),
    pytest.param(ShopOrder, marks=pytest.mark.area_shop),
    pytest.param(DataExportJob, marks=pytest.mark.area_data_export),
]


@pytest.mark.parametrize("model", CASES, ids=lambda model: model._meta.label_lower)
def test_counted_record_has_no_control_add_surface_even_for_superadmin(model, client):
    actor = superadmin("cx7-readonly-control")
    force_recent_control_login(client, actor)
    request = RequestFactory().get("/control/")
    request.user = actor
    registered = admin.site._registry[model]
    assert registered.has_add_permission(request) is False
    before = model.objects.count()
    url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_add")
    assert client.get(url).status_code == 403
    assert client.post(url, {}).status_code == 403
    assert model.objects.count() == before


@pytest.mark.area_notifications
@pytest.mark.area_email
@pytest.mark.parametrize("model", [DailyEmailCounter, DailyNotificationCounter])
def test_daily_worker_counter_has_no_control_creator_route(model, client):
    force_recent_control_login(client, superadmin("cx7-counter-control"))
    assert admin.site.is_registered(model) is False
    path = f"/control/{model._meta.app_label}/{model._meta.model_name}/add/"
    before = model.objects.count()
    assert client.get(path).status_code == 404
    assert client.post(path, {}).status_code == 404
    assert model.objects.count() == before
