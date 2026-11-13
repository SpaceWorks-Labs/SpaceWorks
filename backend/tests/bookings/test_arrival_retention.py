from datetime import timedelta
import pytest
from django.apps import apps
from django.db import connection, transaction
from django.utils import timezone
from apps.bookings.models import BookingCheckInEvent
from apps.bookings.services_arrival import confirm_arrival
from apps.bookings.arrival_projection import arrival_metrics
from apps.data_export.models import EXPORTED_MODELS
from apps.data_export.datasets import DATASET_SPECS
from apps.data_export.fields import FIELDS
from apps.data_export.types import Fidelity, Omitted
from apps.data_export.references import USER_EDGES
from apps.tenant_migration.tenant_dump_catalog import validate_catalog, FIELD_POLICIES
from apps.tenant_migration.tenant_dump_types import AuthorityDisposition
from apps.tenant_migration.omitted_fields import OMITTED_FIELD_RECONSTRUCTIONS, FRESH
from apps.tenant_migration.unique_values import DEPLOYMENT_GLOBAL_UNIQUE_RULES
from tests.bookings.arrival_helpers import world, clock

pytestmark = pytest.mark.django_db


def test_arrival_history_and_projection_have_explicit_portable_policy():
    label = "bookings.BookingCheckInEvent"
    assert label in EXPORTED_MODELS and label in DATASET_SPECS
    for fidelity in Fidelity:
        assert isinstance(FIELDS[(fidelity,"bookings.Booking","checkin_token")],Omitted)
        assert USER_EDGES[(fidelity,label,"actor")].included
    assert OMITTED_FIELD_RECONSTRUCTIONS[("bookings.Booking","checkin_token")] == FRESH
    assert ("bookings.Booking","field:checkin_token") in DEPLOYMENT_GLOBAL_UNIQUE_RULES
    assert FIELD_POLICIES[("bookings.Booking","arrived_at")].dispositions == (AuthorityDisposition.PRESERVE,)
    validate_catalog()


def test_metrics_use_callers_tenant_resource_and_date_predicate(monkeypatch):
    from apps.bookings.models import Booking
    w = world(); other = world("other-arrival-metric"); clock(monkeypatch,w.booking.starts_at)
    confirm_arrival(w.resource,w.credential,actor=w.scanner)
    rows = Booking.objects.filter(space=w.resource,starts_at__gte=w.booking.starts_at,ends_at__lte=w.booking.ends_at)
    assert arrival_metrics(rows) == {"arrived_reservations":1,"confirmed_without_recorded_arrival":0}
    assert arrival_metrics(Booking.objects.filter(space=other.resource)) == {"arrived_reservations":0,"confirmed_without_recorded_arrival":1}


@pytest.mark.django_db(transaction=True)
def test_module_and_whole_tenant_purge_remove_history_without_touching_other_space(monkeypatch):
    from apps.accounts.models import User
    from apps.makerspaces.module_install import uninstall_module
    from apps.makerspaces.module_purge import purge_module
    from apps.makerspaces.lifecycle_purge import purge
    w = world(); other = world("other-arrival-purge")
    # These bookings were created a few microseconds apart; both are in-window here.
    clock(monkeypatch,max(w.booking.starts_at,other.booking.starts_at))
    confirm_arrival(w.resource,w.credential,actor=w.scanner)
    confirm_arrival(other.resource,other.credential,actor=other.scanner)
    root = User.objects.create_superuser(username="arrival-purge-root",email="root@example.test",password="pw")
    uninstall_module(w.tenant,"bookings")
    assert BookingCheckInEvent.objects.filter(booking=w.booking).exists()
    assert purge_module(w.tenant,"bookings",root)["arrivals"] == 1
    assert not BookingCheckInEvent.objects.filter(booking_id=w.booking.pk).exists()
    assert BookingCheckInEvent.objects.filter(booking=other.booking).exists()
    other.tenant.archived_at = timezone.now(); other.tenant.save(update_fields=["archived_at"])
    purge(other.tenant,root)
    assert not BookingCheckInEvent.objects.exists()


def test_bookings_only_feature_catalog_and_installer_prerequisite():
    from apps.makerspaces.capabilities import FEATURES
    from apps.makerspaces.setup_areas import features_for
    for key in ("bookings.confirmations","bookings.checkin"):
        assert FEATURES[key].parent_module == "bookings" and not FEATURES[key].default_enabled
        assert FEATURES[key].requires_modules == ("bookings",)
    assert FEATURES["bookings.checkin"].requires_features == ("bookings.confirmations",)



def test_claim_route_and_pre_auth_guards_accept_all_new_confirmation_routes():
    from apps.accounts.claim_route_guard import validate_claim_route_matrix
    # Validation walks actual mounted views, policy classes and DRF lifecycle hooks.
    validate_claim_route_matrix()


def test_private_headers_wrap_early_error_responses_without_drf_lifecycle_overrides():
    from django.http import HttpResponse
    from django.test import RequestFactory
    from config.request_id import RequestIdMiddleware
    request = RequestFactory().post("/api/v1/public/forge/my-bookings/11111111-1111-1111-1111-111111111111/rotate-checkin/")
    response = RequestIdMiddleware(lambda request: HttpResponse(status=423))(request)
    assert response["Cache-Control"] == "private, no-store"
    assert response["Referrer-Policy"] == "no-referrer"
    assert {"Authorization","Cookie"} <= set(item.strip() for item in response["Vary"].split(","))
