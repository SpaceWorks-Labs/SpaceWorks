"""Global reset-envelope operations never reveal staff identities of unservable tenants."""

import pytest
from django.contrib import admin
from django.http import Http404
from django.test import RequestFactory
from django.urls import resolve, reverse
from django.utils import timezone

from apps.accounts.models import PasswordResetEnvelope, User
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_staff
from tests.accounts.ua1_helpers import merged_shell

pytestmark = pytest.mark.django_db


@pytest.fixture
def envelopes():
    # Decisions 63/66: the hidden row is now an inert shell (a merged account kept for history);
    # live people, with or without a staff row, and the platform account stay visible.
    visible = Makerspace.objects.create(name="Visible", slug="gov-visible")
    root = User.objects.create_superuser(username="gov-envelope-operator")
    users = [
        User.objects.create_user("private-envelope", email="private@example.test"),
        make_staff(visible, username="visible-envelope", email="visible@example.test"),
        User.objects.create_user(username="member-envelope", email="member@example.test"),
        root,
    ]
    rows = [PasswordResetEnvelope.objects.create(user=user,
        context=user.account_kind, makerspace_id=None,
        email_normalized=user.email, email_fingerprint=str(user.pk).zfill(64),
        digest="d" * 64, requested_at=timezone.now()) for user in users]
    merged_shell(users[0], users[1])
    return root, rows


@pytest.mark.parametrize("params", [{}, {"q": "private@example.test"},
    {"o": "1"}, {"o": "-1"}, {"o": "4"}, {"q": "private", "o": "-1"}])
def test_changelist_search_and_ordering_never_reveal_unservable_tenant_staff(envelopes, params):
    root, rows = envelopes
    request = RequestFactory().get(reverse("admin:accounts_passwordresetenvelope_changelist"), params)
    request.user = root
    request.resolver_match = resolve(request.path_info)
    model_admin = admin.site._registry[PasswordResetEnvelope]
    changelist = model_admin.get_changelist_instance(request)
    ids = set(changelist.queryset.values_list("pk", flat=True))
    assert rows[0].pk not in ids
    if "q" not in params:
        assert {row.pk for row in rows[1:]} <= ids


def test_direct_unservable_tenant_staff_envelope_object_is_not_found(envelopes):
    root, rows = envelopes
    request = RequestFactory().get(reverse("admin:accounts_passwordresetenvelope_change", args=[rows[0].pk]))
    request.user = root
    model_admin = admin.site._registry[PasswordResetEnvelope]
    with pytest.raises(Http404):
        model_admin.get_object(request, str(rows[0].pk))
    assert not model_admin.has_view_permission(request, rows[0])
    with pytest.raises(Http404):
        model_admin.change_view(request, str(rows[0].pk))
    for row in rows[1:]:
        assert model_admin.get_object(request, str(row.pk)).pk == row.pk
        assert model_admin.has_view_permission(request, row)
