"""The staff event payload names the currency `payment_amount` is in (audit row 66)."""
import pytest
from rest_framework.test import APIRequestFactory

from apps.events.serializers_event_details import EventAdminSerializer
from tests.events.staff_grant_helpers import grant_fixture

pytestmark = pytest.mark.django_db


def test_admin_event_serializer_carries_the_space_currency():
    from apps.payments.models import MakerspacePaymentSettings
    space, manager, _user, event, _grant = grant_fixture("check_in")
    MakerspacePaymentSettings.objects.update_or_create(makerspace=space, defaults={"default_currency": "inr"})
    request = APIRequestFactory().get("/")
    request.user = manager
    data = EventAdminSerializer(event, context={"request": request}).data
    assert data["currency"] == "inr"
    assert "my_limit" in data and data["my_limit"] is None
