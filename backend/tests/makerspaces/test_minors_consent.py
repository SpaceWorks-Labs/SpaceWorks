"""Decision 223 (k), lane L3b: minors and guardian consent (policy, guard, consent record, routes)."""
from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.makerspaces import community_policy, minors
from apps.makerspaces.community_policy import CommunityError
from apps.makerspaces.minors_guard import evaluate, require_minor_clearance
from apps.makerspaces.models import CommunityPolicy, GuardianConsent, MinorProfile
from tests.makerspaces.l4_helpers import features_off, features_on
from tests.makerspaces.test_membership_j1 import manager, space, user

pytestmark = pytest.mark.django_db(transaction=True)


def _setup(slug="minors-space", *, admitted=True, terms=True, **policy):
    makerspace = space(slug)
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"membership"})
    makerspace.save(update_fields=["enabled_modules"])
    features_on(makerspace, "minors")
    CommunityPolicy.objects.create(makerspace=makerspace, minors_admitted=admitted, **policy)
    staff, child = manager(makerspace), user(f"{slug}-child")
    if terms:
        minors.publish_terms(staff, makerspace, "I consent to my child using the space.", "v1")
    return makerspace, staff, child


def _born(years):
    today = timezone.localdate()
    return today.replace(year=today.year - years, day=1).isoformat()


def _record(makerspace, staff, child, years=15, **extra):
    return minors.record_minor(staff, makerspace, child, date_of_birth=_born(years), **extra)


def _sign(profile, staff, name="A Guardian"):
    return minors.sign_consent(staff, profile, name, accepted=True,
                               method=GuardianConsent.Method.STAFF_RECORDED)


def test_policy_defaults_without_creating_a_row():
    makerspace = space("minors-defaults")
    policy = community_policy.policy_for(makerspace)
    assert (policy.minors_admitted, policy.minors_minimum_age, policy.adult_age) == (False, 13, 18)
    assert policy.guardian_must_be_present and not policy.minors_may_borrow and not policy.minors_may_use_machines
    assert not CommunityPolicy.objects.filter(makerspace=makerspace).exists()


def test_policy_update_is_audited_with_field_names_and_refuses_a_switched_off_feature():
    makerspace, staff, _child = _setup("minors-policy")
    community_policy.update_policy(staff, makerspace, {"minors_minimum_age": 14})
    entry = AuditLog.objects.get(makerspace=makerspace, action="makerspace.community_policy_updated")
    assert entry.meta == {"fields": ["minors_minimum_age"]}
    with pytest.raises(CommunityError) as refused:
        community_policy.update_policy(staff, makerspace, {"volunteer_minutes_per_credit": 60})
    assert refused.value.error_code == "feature_disabled"


def test_guard_is_inert_when_the_capability_is_off_or_the_person_is_not_a_minor():
    makerspace, staff, child = _setup("minors-inert")
    _record(makerspace, staff, child)
    features_off(makerspace, "minors")
    assert evaluate(child, makerspace, "membership") is None
    features_on(makerspace, "minors")
    assert evaluate(user("minors-inert-adult"), makerspace, "membership") is None


def test_a_minor_is_refused_without_a_guardian_consent_then_admitted_with_one():
    makerspace, staff, child = _setup("minors-consent")
    profile = _record(makerspace, staff, child)
    with pytest.raises(CommunityError) as refused:
        require_minor_clearance(child, makerspace, "membership")
    assert refused.value.error_code == "guardian_consent_required"
    _sign(profile, staff)
    require_minor_clearance(child, makerspace, "membership")


def test_a_space_that_does_not_admit_minors_or_sets_a_minimum_age_refuses_them():
    makerspace, staff, child = _setup("minors-closed", admitted=False)
    profile = _record(makerspace, staff, child)
    assert evaluate(child, makerspace, "event")[0] == "minor_not_admitted"
    CommunityPolicy.objects.filter(makerspace=makerspace).update(minors_admitted=True, minors_minimum_age=16)
    assert evaluate(child, makerspace, "event")[0] == "minor_below_minimum_age"
    assert profile.pk


def test_missing_terms_are_a_409_and_new_terms_ask_the_guardian_again():
    makerspace, staff, child = _setup("minors-terms", terms=False)
    profile = _record(makerspace, staff, child)
    assert evaluate(child, makerspace, "membership")[::2] == ("guardian_terms_missing", 409)
    with pytest.raises(CommunityError) as refused:
        _sign(profile, staff)
    assert refused.value.error_code == "guardian_terms_missing"
    minors.publish_terms(staff, makerspace, "First text.", "v1")
    _sign(profile, staff)
    assert evaluate(child, makerspace, "membership") is None
    minors.publish_terms(staff, makerspace, "Second text.", "v2")
    assert evaluate(child, makerspace, "membership")[0] == "guardian_consent_expired"


def test_consent_expires_and_can_be_revoked():
    makerspace, staff, child = _setup("minors-expiry", consent_valid_days=30)
    profile = _record(makerspace, staff, child)
    consent = _sign(profile, staff)
    assert evaluate(child, makerspace, "membership", now=timezone.now() + timedelta(days=31))[0] == "guardian_consent_expired"
    minors.revoke_consent(staff, consent)
    assert evaluate(child, makerspace, "membership")[0] == "guardian_consent_expired"
    assert AuditLog.objects.filter(makerspace=makerspace, action="membership.guardian_consent_revoked").exists()


def test_presence_needs_staff_when_the_guardian_must_be_present_and_borrow_and_machines_follow_the_policy():
    makerspace, staff, child = _setup("minors-purposes")
    _sign(_record(makerspace, staff, child), staff)
    assert evaluate(child, makerspace, "presence")[0] == "guardian_presence_required"
    assert evaluate(child, makerspace, "presence", staff_present=True) is None
    assert evaluate(child, makerspace, "borrow")[0] == "minor_borrowing_not_allowed"
    assert evaluate(child, makerspace, "machine")[0] == "minor_machines_not_allowed"
    CommunityPolicy.objects.filter(makerspace=makerspace).update(
        minors_may_borrow=True, minors_may_use_machines=True, guardian_must_be_present=False)
    assert evaluate(child, makerspace, "borrow") is None and evaluate(child, makerspace, "machine") is None
    assert evaluate(child, makerspace, "presence") is None


def test_record_minor_stores_the_minimum_validates_and_audits_without_pii():
    makerspace, staff, child = _setup("minors-record")
    guardian = user("minors-record-guardian")
    profile = _record(makerspace, staff, child, guardian_user=guardian, guardian_name="Pat Guardian",
                      guardian_email="Pat@Example.test")
    assert profile.guardian_email == "pat@example.test" and minors.age_of(profile) == 15
    entry = AuditLog.objects.get(makerspace=makerspace, action="membership.minor_recorded")
    assert entry.meta == {"created": True, "has_guardian_account": True}
    assert "Pat" not in str(entry.meta) and profile.date_of_birth not in str(entry.meta)
    with pytest.raises(Exception):
        minors.record_minor(staff, makerspace, user("minors-adult"), date_of_birth=_born(30))
    with pytest.raises(Exception):
        minors.record_minor(staff, makerspace, user("minors-future"), date_of_birth=(date.today() + timedelta(days=5)).isoformat())
    declared = minors.record_minor(staff, makerspace, user("minors-declared"), declared_under_age=True)
    assert declared.date_of_birth == "" and minors.age_of(declared) is None
    cleared = minors.clear_minor(staff, profile)
    assert cleared.cleared_at is not None and evaluate(child, makerspace, "membership") is None


def test_only_the_named_guardian_can_sign_in_their_own_account_and_the_signature_is_idempotent():
    makerspace, staff, child = _setup("minors-guardian")
    guardian, stranger = user("minors-g-account"), user("minors-g-stranger")
    profile = _record(makerspace, staff, child, guardian_user=guardian)
    with pytest.raises(CommunityError) as refused:
        minors.sign_consent(stranger, profile, "Not Me", accepted=True, method=GuardianConsent.Method.GUARDIAN_ACCOUNT)
    assert refused.value.error_code == "not_the_guardian"
    first = minors.sign_consent(guardian, profile, "Guardian Person", accepted=True,
                                method=GuardianConsent.Method.GUARDIAN_ACCOUNT, operation_id="op-1")
    again = minors.sign_consent(guardian, profile, "Guardian Person", accepted=True,
                                method=GuardianConsent.Method.GUARDIAN_ACCOUNT, operation_id="op-1")
    assert first.pk == again.pk and GuardianConsent.objects.filter(profile=profile).count() == 1
    with pytest.raises(CommunityError):
        minors.sign_consent(guardian, profile, "", accepted=True, method=GuardianConsent.Method.GUARDIAN_ACCOUNT)
    with pytest.raises(RuntimeError):
        first.delete()


def _connect(makerspace, *people):
    """Audit M9: the staff route only resolves people already tied to the space (here, a membership row)."""
    from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
    role = MakerspaceRole.objects.get(makerspace=makerspace, slug="member")
    for person in people:
        MakerspaceMembership.objects.create(makerspace=makerspace, user=person, assigned_role=role,
                                            role="custom", status="active")


def test_minor_record_route_does_not_resolve_unconnected_accounts():
    makerspace, staff, _child = _setup("minors-oracle")
    stranger = user("minors-oracle-stranger")
    stranger.display_name = "Oracle Stranger"
    stranger.save(update_fields=["display_name"])
    client = APIClient()
    client.force_authenticate(staff)
    refused = client.post(f"/api/v1/admin/makerspaces/{makerspace.pk}/minors", {
        "user_id": stranger.pk, "date_of_birth": _born(12)}, format="json")
    assert refused.status_code == 404 and stranger.display_name not in str(refused.data)
    assert not MinorProfile.objects.filter(makerspace=makerspace, user=stranger).exists()


def test_staff_and_guardian_routes_round_trip():
    makerspace, staff, child = _setup("minors-http")
    guardian = user("minors-http-guardian")
    _connect(makerspace, child, guardian)
    staff_client = APIClient()
    staff_client.force_authenticate(staff)
    created = staff_client.post(f"/api/v1/admin/makerspaces/{makerspace.pk}/minors", {
        "user_id": child.pk, "date_of_birth": _born(12), "guardian_user_id": guardian.pk}, format="json")
    assert created.status_code == 201 and "date_of_birth" not in created.data
    profile_id = created.data["id"]
    guardian_client = APIClient()
    guardian_client.force_authenticate(guardian)
    page = guardian_client.get(f"/api/v1/member/makerspaces/{makerspace.pk}/guardian-consents")
    assert page.status_code == 200 and page.data["dependents"][0]["profile_id"] == profile_id
    signed = guardian_client.post(
        f"/api/v1/member/makerspaces/{makerspace.pk}/guardian-consents/{profile_id}/sign",
        {"signed_name": "Guardian Person", "accepted": True}, format="json")
    assert signed.status_code == 201
    listing = staff_client.get(f"/api/v1/admin/makerspaces/{makerspace.pk}/minors")
    assert listing.data["results"][0]["consent_state"] == "valid"
    revoked = guardian_client.post(
        f"/api/v1/member/makerspaces/{makerspace.pk}/guardian-consents/{profile_id}/revoke")
    assert revoked.status_code == 200
    features_off(makerspace, "minors")
    assert staff_client.get(f"/api/v1/admin/makerspaces/{makerspace.pk}/minors").status_code == 404
    assert MinorProfile.objects.filter(pk=profile_id).exists()  # data kept while the switch is off


def test_publish_terms_unique_violation_is_a_typed_409(monkeypatch):
    """Final audit 0.12.0 (m22): a lost publish race maps to 409, not an unhandled IntegrityError."""
    from django.db import IntegrityError
    from apps.makerspaces.models import GuardianConsentTerms
    makerspace, staff, _child = _setup("minors-terms-race")

    def boom(*args, **kwargs):
        raise IntegrityError("guardian_terms_version_unique")
    monkeypatch.setattr(GuardianConsentTerms.objects, "create", boom)
    with pytest.raises(minors.GuardianTermsConflict) as caught:
        minors.publish_terms(staff, makerspace, "New consent text.", "v2")
    assert caught.value.status_code == 409
