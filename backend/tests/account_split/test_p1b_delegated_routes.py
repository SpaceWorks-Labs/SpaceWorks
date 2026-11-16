"""The registry is complete, explicit and does not implement runtime policy."""

from types import ModuleType

import pytest
from django.core.checks import Tags, run_checks
from django.http import HttpResponse
from django.test import override_settings
from django.urls import include, path, re_path

from apps.accounts.checks import check_delegated_routes
from apps.accounts.delegated_routes import (
    DELEGABLE, MEMBER_ONLY, MEMBERSHIP_ONLY, SHARED_ACCOUNT_UTILITY, route_class,
)
from apps.accounts.delegated_route_catalog import DELEGABLE_ROUTES, MEMBERSHIP_ROUTES, SHARED_ROUTES


def test_current_urlconf_has_no_unclassified_staff_routes():
    assert check_delegated_routes() == []


def test_classification_sets_do_not_overlap():
    assert not MEMBERSHIP_ROUTES & DELEGABLE_ROUTES
    assert not MEMBERSHIP_ROUTES & SHARED_ROUTES
    assert not DELEGABLE_ROUTES & SHARED_ROUTES


@pytest.mark.parametrize(("name", "classification"), [
    ("admin-inventory", DELEGABLE),
    ("admin-inventory-detail", DELEGABLE),
    ("admin-accessible-events", DELEGABLE),
    ("admin-accessible-booking-spaces", DELEGABLE),
    ("admin-event-check-in-resolve", DELEGABLE),
    ("admin-booking-arrival-resolve", DELEGABLE),
    ("admin-organization-membership-detail", DELEGABLE),
    ("auth-staff-invitation-accept", MEMBER_ONLY),  # U-B: a person redeems their own invitation
    ("tenant-bootstrap", DELEGABLE),
    ("auth-me", SHARED_ACCOUNT_UTILITY),
    ("auth-change-password", SHARED_ACCOUNT_UTILITY),
    ("auth-mfa", SHARED_ACCOUNT_UTILITY),
    ("contract-preferences", SHARED_ACCOUNT_UTILITY),
    ("contract-endpoint-revoke", SHARED_ACCOUNT_UTILITY),
    ("admin-device-enrollment-create", MEMBERSHIP_ONLY),
    ("admin-platform-dashboard", MEMBERSHIP_ONLY),
])
def test_authority_source_examples(name, classification):
    assert route_class(name) == classification


def test_unknown_names_fail_closed_without_loading_django_models():
    assert route_class("future-staff-route") is None
    assert route_class(None) is None


@pytest.mark.parametrize("name", ["unclassified-staff-route", None])
def test_system_check_rejects_new_and_unnamed_nested_staff_routes(name):
    urlconf = ModuleType("account_split_test_urls")
    urlconf.urlpatterns = [path("api/v1/admin/", include([
        path("future/", lambda request: HttpResponse(), name=name),
    ]))]
    with override_settings(ROOT_URLCONF=urlconf):
        errors = [error for error in run_checks(tags=[Tags.urls]) if error.id == "accounts.E001"]
    assert len(errors) == 1
    assert "/api/v1/admin/future/" in errors[0].msg


def test_public_route_does_not_need_staff_classification():
    urlconf = ModuleType("account_split_public_test_urls")
    urlconf.urlpatterns = [path("api/v1/public/future/", lambda request: HttpResponse(), name="public-future")]
    with override_settings(ROOT_URLCONF=urlconf):
        assert check_delegated_routes() == []


def test_regex_staff_route_cannot_bypass_the_check():
    urlconf = ModuleType("account_split_regex_test_urls")
    urlconf.urlpatterns = [re_path(r"^api/v1/admin/future/$", lambda request: HttpResponse(),
                                  name="future-regex-route")]
    with override_settings(ROOT_URLCONF=urlconf):
        assert [error.id for error in check_delegated_routes()] == ["accounts.E001"]
