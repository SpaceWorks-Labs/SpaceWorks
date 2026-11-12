from datetime import timedelta
from pathlib import Path
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, NotFound
from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.models_profiles import PublicHandle, PublicHandleRedirect, MemberProfile
from apps.makerspaces.public_profile_handles import claim_handle, release_handle, normalize_handle
from django.contrib.auth.models import AnonymousUser
from apps.makerspaces.account_profile_access import resolve_by_handle
from apps.makerspaces.public_profile_route_inventory import route_segments
from apps.makerspaces.public_profile_reserved import RESERVED_SEGMENTS

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("name", ["ab", "a" * 31, "-abc", "abc.", "a b", "a/b", "a@b", "a\nb", "abc\n", "éabc"])
def test_invalid_grammar(name):
    with pytest.raises(ValidationError):
        normalize_handle(name)


@pytest.mark.parametrize("name", ["abc", "a.b", "a_b", "a-b", "a" * 30, "A.B"])
def test_valid_names(name):
    assert normalize_handle(name) == name.lower()


@pytest.mark.parametrize("name", ["admin", "api", "share", "mfa", "member", "events", "robots.txt", "control"])
def test_reserved(name):
    with pytest.raises(ValidationError):
        normalize_handle(name)


def test_reserved_route_drift_guard():
    root = Path(__file__).resolve().parents[3]
    missing = route_segments(root) - RESERVED_SEGMENTS
    assert not missing, f"Reserve these new top-level routes before shipping: {sorted(missing)}"


def test_drift_guard_detects_new_root_in_empty_backend_include(tmp_path):
    (tmp_path / "frontend/src").mkdir(parents=True)
    (tmp_path / "backend/config").mkdir(parents=True)
    (tmp_path / "deploy").mkdir()
    (tmp_path / "frontend/src/AppRoutes.tsx").write_text('<Route path="/new-front" />')
    (tmp_path / "frontend/nginx.conf").write_text('location /new-proxy/ { }')
    (tmp_path / "backend/config/urls.py").write_text('path("", include("config.extra"))')
    (tmp_path / "backend/config/extra.py").write_text('path("new-back/", view)')
    assert {"new-front", "new-proxy", "new-back"} <= route_segments(tmp_path)


def test_collision_is_case_insensitive_at_service_and_database(membership):
    claim = claim_handle(membership.user, "Maker.Name")
    user = User.objects.create_user(username="second-maker")
    other = MakerspaceMembership.objects.create(user=user, makerspace=membership.makerspace, assigned_role=membership.makerspace.roles.get(slug="member"), role="custom")
    with pytest.raises(ValidationError):
        claim_handle(other.user, "MAKER.NAME")
    with pytest.raises(IntegrityError), transaction.atomic():
        PublicHandle.objects.create(user=user, profile=MemberProfile.objects.create(membership=other),
                                    handle=claim.handle, changed_at=timezone.now())


def test_change_cooldown_redirect_release_and_reuse(published):
    membership = published.membership
    with pytest.raises(ValidationError):
        claim_handle(membership.user, "new.maker")
    PublicHandle.objects.filter(user=membership.user).update(changed_at=timezone.now() - timedelta(days=31))
    claim_handle(membership.user, "new.maker")
    current, redirected = resolve_by_handle("public.maker", AnonymousUser())
    assert redirected == "new.maker" and current.user_id == membership.user_id
    release_handle(membership.user)
    with pytest.raises(NotFound):
        resolve_by_handle("public.maker", AnonymousUser())
    with pytest.raises(ValidationError):
        claim_handle(membership.user, "another.maker")
    PublicHandleRedirect.objects.all().update(expires_at=timezone.now() - timedelta(seconds=1))
    claim_handle(membership.user, "public.maker")
    with pytest.raises(NotFound):
        resolve_by_handle("public.maker", AnonymousUser())  # release cleared publication consent


def test_retired_handle_is_unavailable_to_another_account(published):
    membership = published.membership
    release_handle(membership.user)
    user = User.objects.create_user(username="handle-squatter")
    other = MakerspaceMembership.objects.create(user=user, makerspace=membership.makerspace, assigned_role=membership.makerspace.roles.get(slug="member"), role="custom")
    with pytest.raises(ValidationError):
        claim_handle(other.user, "PUBLIC.MAKER")
    PublicHandleRedirect.objects.all().update(expires_at=timezone.now() - timedelta(seconds=1))
    assert claim_handle(other.user, "public.maker").user == user


@pytest.mark.django_db(transaction=True)
def test_concurrent_first_claims_have_one_winner(membership):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import close_old_connections
    other = MakerspaceMembership.objects.create(
        user=User.objects.create_user(username="concurrent-maker"), makerspace=membership.makerspace, assigned_role=membership.makerspace.roles.get(slug="member"), role="custom")
    barrier = Barrier(2)
    def attempt(pk):
        close_old_connections()
        try:
            member = MakerspaceMembership.objects.select_related("user", "makerspace").get(pk=pk)
            barrier.wait(timeout=10)
            try:
                claim_handle(member.user, "concurrent.name")
                return "claimed"
            except ValidationError:
                return "collision"
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [membership.pk, other.pk]))
    assert sorted(results) == ["claimed", "collision"]
    assert PublicHandle.objects.filter(handle="concurrent.name").count() == 1
