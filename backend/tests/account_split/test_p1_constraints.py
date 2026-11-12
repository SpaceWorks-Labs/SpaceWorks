import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MembershipAdditionalRole
from .p1_helpers import flush_constraints, raw_membership, sql, staff

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def spaces():
    return [Makerspace.objects.create(name=slug, slug=slug) for slug in ("split-a", "split-b")]


@pytest.mark.parametrize("values", [
    {"account_kind": "unknown"},
    {"account_kind": "staff"},
    {"account_kind": "member", "staff_makerspace_id": "space"},
    {"account_kind": "platform", "is_superuser": False, "role": "superadmin"},
    {"account_kind": "platform", "is_superuser": True, "role": "requester"},
    {"account_kind": "member", "is_superuser": True},
    {"account_kind": "staff", "staff_makerspace_id": "space", "is_superuser": True},
    {"account_kind": "member", "role": "superadmin"},
    {"account_kind": "staff", "retired_at": "now", "is_active": True},
    {"account_kind": "member", "retired_at": "now", "is_active": False},
    {"credential_generation": -1},
])
def test_context_checks_reject_raw_inserts(spaces, values):
    values = {key: spaces[0].pk if value == "space" else timezone.now() if value == "now" else value
              for key, value in values.items()}
    # Use a normal row only as an INSERT template; bypass the manager and model save guards.
    template = User.objects.create_user("template")
    fields = [field for field in User._meta.concrete_fields if not field.primary_key]
    payload = {field.column: getattr(template, field.attname) for field in fields}
    payload.update(values)
    payload["username"] = "invalid"
    columns = ", ".join(f'"{column}"' for column in payload)
    with pytest.raises(IntegrityError), transaction.atomic():
        sql(f"INSERT INTO accounts_user ({columns}) VALUES ({', '.join(['%s'] * len(payload))})",
            list(payload.values()))
        flush_constraints()


@pytest.mark.parametrize("mutation", [
    # Decision 63 (one account per person): the staff -> member retarget premise is retired, so the
    # raw kind change now probed is the reverse one (person -> shell), which only a unification run may do.
    "UPDATE accounts_user SET account_kind = 'staff' WHERE id = %s",
    "UPDATE accounts_user SET staff_makerspace_id = %s WHERE id = %s",
    "UPDATE accounts_user SET staff_makerspace_id = NULL, retired_at = CURRENT_TIMESTAMP, is_active = false WHERE id = %s",
    "DELETE FROM accounts_user WHERE id = %s",
])
def test_raw_context_retargeting_and_staff_hard_delete_are_refused(spaces, mutation):
    user, _ = staff(spaces[0])
    params = [spaces[1].pk, user.pk] if mutation.count("%s") == 2 else [user.pk]
    with pytest.raises(IntegrityError), transaction.atomic():
        sql(mutation, params)


def test_staff_creation_is_deferred_and_requires_complete_membership(spaces):
    # Decision 63: no new "staff" accounts; a person becomes staff by holding a staff-track
    # membership, whose built-in staff role is validated by a deferred constraint trigger.
    with pytest.raises(ValueError):
        User.objects.create_user("orphan", account_kind="staff", staff_makerspace=spaces[0])
    person = User.objects.create_user("complete")
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.staff_tracks.create(
            user=person, makerspace=spaces[0], role="custom", track="staff",
            assigned_role=spaces[0].roles.get(slug="member"))
        flush_constraints()
    with transaction.atomic():
        MakerspaceMembership.staff_tracks.create(
            user=person, makerspace=spaces[0], role="handover", track="staff",
            assigned_role=spaces[0].roles.get(slug="handover"))
    assert MakerspaceMembership.staff_tracks.filter(user=person).count() == 1


@pytest.mark.parametrize("kind,slug", [("member", "space_manager"), ("member", "handover"),
                                     ("platform", "member"), ("platform", "space_manager")])
def test_member_and_platform_raw_membership_insert_refused(spaces, kind, slug):
    user = User.objects.create_superuser("root") if kind == "platform" else User.objects.create_user("member")
    _, template = staff(spaces[0], role="handover")
    # Decision 63: a person may hold staff roles on a staff-track row, so for a member-kind account
    # the refused shape is a COMMUNITY row carrying a staff role. A platform account holds no rows.
    track = {"track": "community"} if kind == "member" else {}
    with pytest.raises(IntegrityError), transaction.atomic():
        raw_membership(template, user_id=user.pk, assigned_role_id=spaces[0].roles.get(slug=slug).pk, **track)
        flush_constraints()


@pytest.mark.parametrize("field,value", [
    ("assigned_role_id", "member"), ("assigned_role_id", None),
    ("assigned_role_id", "foreign"), ("makerspace_id", "foreign"), ("status", "pending"),
])
def test_staff_membership_updates_refused(spaces, field, value):
    user, membership = staff(spaces[0])
    if value == "member": value = spaces[0].roles.get(slug="member").pk
    elif value == "foreign":
        value = spaces[1].pk if field == "makerspace_id" else spaces[1].roles.get(slug="inventory_manager").pk
    with pytest.raises(IntegrityError), transaction.atomic():
        sql(f'UPDATE makerspaces_makerspacemembership SET "{field}"=%s WHERE id=%s', [value, membership.pk])
        flush_constraints()


def test_staff_second_membership_and_delete_refused(spaces):
    user, membership = staff(spaces[0])
    # Decision 63/286: accounts are global, so a person may hold a staff row in another space;
    # a second staff-track row in the SAME space is what stays refused (unique per track).
    with pytest.raises(IntegrityError), transaction.atomic():
        raw_membership(membership, user_id=user.pk, assigned_role_id=spaces[0].roles.get(slug="handover").pk)
    with pytest.raises(IntegrityError), transaction.atomic():
        sql("DELETE FROM makerspaces_makerspacemembership WHERE id=%s", [membership.pk])


@pytest.mark.parametrize("slug,primary", [("member", "inventory_manager"), ("space_manager", "handover"),
                                         ("handover", "space_manager"), ("foreign", "handover"),
                                         ("handover", "handover")])
def test_invalid_raw_additional_role_insert_refused(spaces, slug, primary):
    _, membership = staff(spaces[0], role=primary)
    role = spaces[1].roles.get(slug="handover") if slug == "foreign" else spaces[0].roles.get(slug=slug)
    with pytest.raises(IntegrityError), transaction.atomic():
        sql("INSERT INTO makerspaces_membershipadditionalrole (membership_id,role_id,assigned_at) VALUES (%s,%s,CURRENT_TIMESTAMP)",
            [membership.pk, role.pk])


def test_additional_role_rewrite_can_be_temporarily_invalid(spaces):
    _, membership = staff(spaces[0], role="handover")
    with transaction.atomic():
        link = MembershipAdditionalRole.objects.create(membership=membership, role=spaces[0].roles.get(slug="member"))
        sql("UPDATE makerspaces_membershipadditionalrole SET role_id=%s WHERE id=%s",
            [spaces[0].roles.get(slug="machine_manager").pk, link.pk])


@pytest.mark.parametrize("direction", ["old", "new"])
def test_additional_role_membership_reassignment_checks_both_users(spaces, direction):
    _, source = staff(spaces[0], "source", role="inventory_manager")
    _, target = staff(spaces[0], "target", role="inventory_manager")
    link = MembershipAdditionalRole.objects.create(membership=source, role=spaces[0].roles.get(slug="handover"))
    with pytest.raises(IntegrityError), transaction.atomic():
        # Emulate pre-existing corruption without scheduling a membership validation.
        # Only the additional-link trigger can detect it in this transaction.
        sql("ALTER TABLE makerspaces_makerspacemembership DISABLE TRIGGER accounts_membership_valid")
        sql("UPDATE makerspaces_makerspacemembership SET status='invalid' WHERE id=%s",
            [source.pk if direction == "old" else target.pk])
        sql("ALTER TABLE makerspaces_makerspacemembership ENABLE TRIGGER accounts_membership_valid")
        sql("UPDATE makerspaces_membershipadditionalrole SET membership_id=%s WHERE id=%s", [target.pk, link.pk])


def test_additional_role_delete_revalidates_old_user(spaces):
    _, membership = staff(spaces[0])
    link = MembershipAdditionalRole.objects.create(membership=membership, role=spaces[0].roles.get(slug="handover"))
    with pytest.raises(IntegrityError), transaction.atomic():
        sql("ALTER TABLE makerspaces_makerspacemembership DISABLE TRIGGER accounts_membership_valid")
        sql("UPDATE makerspaces_makerspacemembership SET status='invalid' WHERE id=%s", [membership.pk])
        sql("ALTER TABLE makerspaces_makerspacemembership ENABLE TRIGGER accounts_membership_valid")
        sql("DELETE FROM makerspaces_membershipadditionalrole WHERE id=%s", [link.pk])


def test_both_sides_of_membership_user_reassignment_are_validated(spaces):
    first, membership = staff(spaces[0])
    # NEW side: a staff row handed to a platform account is invalid.
    platform = User.objects.create_superuser("platform-root")
    with pytest.raises(IntegrityError), transaction.atomic():
        sql("UPDATE makerspaces_makerspacemembership SET user_id=%s WHERE id=%s", [platform.pk, membership.pk])
    # OLD side: the user losing the row is re-validated too (decision 63: a person left with no
    # rows is valid, so the old user is given a second, already corrupted row to be caught).
    other = User.objects.create_user("other-person")
    second = MakerspaceMembership.staff_tracks.create(
        user=first, makerspace=spaces[1], role="handover", track="staff",
        assigned_role=spaces[1].roles.get(slug="handover"))
    with pytest.raises(IntegrityError), transaction.atomic():
        sql("ALTER TABLE makerspaces_makerspacemembership DISABLE TRIGGER accounts_membership_valid")
        sql("UPDATE makerspaces_makerspacemembership SET status='invalid' WHERE id=%s", [second.pk])
        sql("ALTER TABLE makerspaces_makerspacemembership ENABLE TRIGGER accounts_membership_valid")
        sql("UPDATE makerspaces_makerspacemembership SET user_id=%s WHERE id=%s", [other.pk, membership.pk])


@pytest.mark.parametrize("guc", ["", "wrong", "correct"])
def test_exact_tenant_retirement_and_one_way_shell(spaces, guc):
    # Decision 63: purging a tenant deletes its staff-track rows (exact-tenant GUC only); the
    # person account itself is never retired or retargeted by it.
    user, membership = staff(spaces[0])
    setting = "" if not guc else str(spaces[guc == "wrong"].pk)
    def retire():
        sql("SELECT set_config('app.account_retirement_makerspace_id',%s,true)", [setting])
        sql("DELETE FROM makerspaces_makerspacemembership WHERE id=%s", [membership.pk])
    if guc != "correct":
        with pytest.raises(IntegrityError), transaction.atomic(): retire()
        return
    with transaction.atomic(): retire()
    user.refresh_from_db()
    assert user.is_active and user.retired_at is None and user.account_kind == "member"
    assert not MakerspaceMembership.staff_tracks.filter(user=user).exists()
    for statement in (
        "UPDATE accounts_user SET retired_at=NULL,staff_makerspace_id=%s WHERE id=%s",
        "UPDATE accounts_user SET staff_makerspace_id=%s WHERE id=%s",
    ):
        with pytest.raises(IntegrityError), transaction.atomic(): sql(statement, [spaces[0].pk, user.pk])
    with pytest.raises(IntegrityError), transaction.atomic():
        sql("UPDATE accounts_user SET retired_at=CURRENT_TIMESTAMP,is_active=false WHERE id=%s", [user.pk])


def test_retirement_guc_does_not_allow_deleting_live_staff_membership(spaces):
    # Only the EXACT tenant's purge authority may delete a staff-track row; another tenant's
    # purge GUC and a unification-run GUC do not (the correct-tenant case is covered above).
    _, membership = staff(spaces[0])
    with pytest.raises(IntegrityError), transaction.atomic():
        sql("SELECT set_config('app.account_retirement_makerspace_id',%s,true)", [str(spaces[1].pk)])
        sql("SELECT set_config('app.account_unification_run_id',%s,true)", ["1"])
        sql("DELETE FROM makerspaces_makerspacemembership WHERE id=%s", [membership.pk])
