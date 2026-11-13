"""Sign-in credentials travel with a space's people (#128 C-18, #137 Q-B1; local only).

A created person signs in on the target with the travelled password and authenticator; a
linked person keeps the target's credentials; nothing in the archive is plaintext; and
sessions and device grants never travel.
"""

import pytest
from django.contrib.auth.hashers import check_password

from apps.accounts.mfa_crypto import new_secret
from apps.accounts.models import User
from apps.accounts.models_mfa import UserMFA
from apps.accounts.models_webauthn import WebAuthnCredential
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.secrets import decrypt_value, encrypt_value
from apps.tenant_migration.credential_block import BLOCK_PATH, write_credential_block
from apps.tenant_migration.materialization import materialize_tenant
from tests.accounts.account_factories import grant_staff_role, make_membership
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case

pytestmark = pytest.mark.django_db(transaction=True)

SECRET = new_secret()


def _person_with_credentials(space, username):
    person = make_user(username)
    User.objects.filter(pk=person.pk).update(email="")  # the target never saw this address
    person.refresh_from_db()
    person.set_password("travelled-password-1")
    person.save(update_fields=["password"])
    make_membership(person, space)
    grant_staff_role(person, space, role_slug="machine_manager")
    UserMFA.objects.create(user=person, secret=encrypt_value(SECRET), enabled_at=person.date_joined,
                           recovery_digests=["pbkdf2_sha256$1$salt$digest"])
    WebAuthnCredential.objects.create(user=person, credential_id=f"cred-{username}", public_key=b"\x01\x02",
                                      rp_id="lab.example.test", name="Laptop")
    return person


@pytest.mark.parametrize("decision", ["create", "link"])
def test_credentials_travel_to_created_people_only(settings, decision):
    settings.PUBLIC_APP_BASE_URL = "https://lab.example.test"
    with enabled_encryption():
        owner = make_user(f"ct-owner-{decision}")
        source = make_space(f"ct-{decision}")
        existing = make_user(f"ct-existing-{decision}")
        state = {}

        def prepare(space, _user, _request):
            state["person"] = _person_with_credentials(space, f"ct-person-{decision}")

        with portable_import_case(source, owner, prepare_source=prepare) as case:
            assert write_credential_block(case.root, source, case.carried) >= 1
            text = (case.root / BLOCK_PATH).read_text(encoding="utf-8")
            assert SECRET not in text and "travelled-password" not in text
            assert state["person"].password not in text
            assert "pbkdf2_sha256$1$salt$digest" not in text and "cred-ct-person" not in text
            # A different deployment never saw these passkeys.
            WebAuthnCredential.objects.filter(user=state["person"]).delete()
            case.decide_walk_in(owner)
            if decision == "create":
                case.decide_walk_in(state["person"])
            else:
                case.decide_link(state["person"], existing)
            result = materialize_tenant(case.root, case.job, case.carried,
                                        target_identity={"slug": f"ct-target-{decision}"})
        target = Makerspace.objects.get(pk=result.target_makerspace_id)
        holder = MakerspaceMembership.staff_tracks.get(makerspace=target).user
        if decision == "create":
            assert holder.pk != state["person"].pk and not holder.is_walk_in
            assert check_password("travelled-password-1", holder.password)
            mfa = UserMFA.objects.get(user=holder)
            assert decrypt_value(mfa.secret) == SECRET and mfa.enabled_at is not None
            assert mfa.recovery_digests == ["pbkdf2_sha256$1$salt$digest"]
            assert list(WebAuthnCredential.objects.filter(user=holder).values_list("rp_id", flat=True)) == [
                "lab.example.test"]
            assert MakerspaceMembership.staff_tracks.get(makerspace=target).status == "active"
            assert result.identities_created >= 2
        else:
            assert holder.pk == existing.pk
            assert not existing.has_usable_password() or not check_password("travelled-password-1", existing.password)
            assert not UserMFA.objects.filter(user=existing).exists()
        from django.apps import apps
        for label in ("accounts.DeviceGrant", "accounts.DeviceRefreshFamily", "token_blacklist.OutstandingToken"):
            assert not apps.get_model(label)._base_manager.filter(user=holder).exists()


def test_a_passkey_for_another_domain_stays_behind(settings):
    from apps.tenant_migration.credential_block import install_credentials

    settings.PUBLIC_APP_BASE_URL = "https://other.example.test"
    space = make_space("ct-domain")
    person = make_user("ct-domain-person")
    installed = install_credentials(person, {"passkeys": [{
        "credential_id": "cred-domain", "public_key": "0102", "rp_id": "lab.example.test"}]}, target=space)
    assert installed == 0 and not WebAuthnCredential.objects.filter(user=person).exists()


def test_a_source_without_a_dek_carries_no_block(tmp_path):
    space = make_space("ct-plain")
    (tmp_path / "global").mkdir()
    (tmp_path / "global" / "users.csv").write_text("id,account_kind\n1,member\n", encoding="utf-8")
    assert write_credential_block(tmp_path, space, [{"version": 1, "status": "active"}]) == 0
    assert not (tmp_path / BLOCK_PATH).exists()
