"""Commit-time account membership validation, including both sides of reassignment."""

from django.db import migrations


SQL = r"""
CREATE FUNCTION accounts_guard_context() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.account_kind = 'staff' THEN
            RAISE EXCEPTION 'Staff accounts must be retired, never deleted' USING ERRCODE = '23514';
        END IF;
        RETURN OLD;
    END IF;
    IF NEW.account_kind IS DISTINCT FROM OLD.account_kind THEN
        RAISE EXCEPTION 'Account kind is immutable' USING ERRCODE = '23514';
    END IF;
    IF NEW.staff_makerspace_id IS DISTINCT FROM OLD.staff_makerspace_id
       OR NEW.retired_at IS DISTINCT FROM OLD.retired_at THEN
        IF NOT (OLD.account_kind = 'staff' AND OLD.staff_makerspace_id IS NOT NULL
            AND OLD.retired_at IS NULL AND NEW.staff_makerspace_id IS NULL
            AND NEW.retired_at IS NOT NULL AND NEW.is_active = false
            AND current_setting('app.account_retirement_makerspace_id', true)
                IS NOT DISTINCT FROM OLD.staff_makerspace_id::text) THEN
            RAISE EXCEPTION 'Account context is immutable outside exact-tenant retirement'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER accounts_user_context_immutable BEFORE UPDATE OR DELETE ON accounts_user
    FOR EACH ROW EXECUTE FUNCTION accounts_guard_context();

CREATE FUNCTION accounts_validate_memberships(subject_id bigint) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    subject accounts_user%ROWTYPE;
    membership makerspaces_makerspacemembership%ROWTYPE;
    primary_role makerspaces_makerspacerole%ROWTYPE;
    role_count integer;
BEGIN
    SELECT * INTO subject FROM accounts_user WHERE id = subject_id FOR UPDATE;
    IF NOT FOUND THEN RETURN; END IF;
    SELECT count(*) INTO role_count FROM makerspaces_makerspacemembership WHERE user_id = subject_id;
    IF subject.account_kind = 'platform' OR subject.retired_at IS NOT NULL THEN
        IF role_count <> 0 THEN
            RAISE EXCEPTION 'Platform and retired accounts cannot hold memberships' USING ERRCODE = '23514';
        END IF;
        RETURN;
    END IF;
    IF subject.account_kind = 'staff' AND role_count <> 1 THEN
        RAISE EXCEPTION 'Staff accounts require exactly one membership' USING ERRCODE = '23514';
    END IF;
    FOR membership IN SELECT * FROM makerspaces_makerspacemembership WHERE user_id = subject_id LOOP
        SELECT * INTO primary_role FROM makerspaces_makerspacerole WHERE id = membership.assigned_role_id;
        IF NOT FOUND OR primary_role.makerspace_id <> membership.makerspace_id
            OR NOT primary_role.is_default OR NOT primary_role.is_protected
            OR membership.status NOT IN ('active', 'revoked') THEN
            RAISE EXCEPTION 'Membership requires a same-tenant built-in role and valid status'
                USING ERRCODE = '23514';
        END IF;
        IF subject.account_kind = 'staff' THEN
            IF membership.makerspace_id <> subject.staff_makerspace_id
                OR primary_role.slug NOT IN ('space_manager', 'inventory_manager', 'machine_manager',
                                             'event_manager', 'booking_manager', 'handover') THEN
                RAISE EXCEPTION 'Staff membership context mismatch' USING ERRCODE = '23514';
            END IF;
        ELSIF subject.account_kind = 'member' AND primary_role.slug <> 'member' THEN
            RAISE EXCEPTION 'Member accounts can hold only Member roles' USING ERRCODE = '23514';
        END IF;
        IF EXISTS (
            SELECT 1 FROM makerspaces_membershipadditionalrole link
            JOIN makerspaces_makerspacerole role ON role.id = link.role_id
            WHERE link.membership_id = membership.id AND (
                subject.account_kind <> 'staff' OR primary_role.slug = 'space_manager'
                OR role.makerspace_id <> membership.makerspace_id
                OR NOT role.is_default OR NOT role.is_protected
                OR role.slug NOT IN ('inventory_manager', 'machine_manager', 'event_manager',
                                     'booking_manager', 'handover')
                OR role.id = primary_role.id
            )
        ) THEN
            RAISE EXCEPTION 'Invalid additional membership role' USING ERRCODE = '23514';
        END IF;
    END LOOP;
END $$;

CREATE FUNCTION accounts_membership_constraint() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    old_user bigint;
    new_user bigint;
BEGIN
    IF TG_TABLE_NAME = 'accounts_user' THEN
        IF TG_OP <> 'INSERT' THEN old_user := OLD.id; END IF;
        IF TG_OP <> 'DELETE' THEN new_user := NEW.id; END IF;
    ELSIF TG_TABLE_NAME = 'makerspaces_makerspacemembership' THEN
        IF TG_OP <> 'INSERT' THEN old_user := OLD.user_id; END IF;
        IF TG_OP <> 'DELETE' THEN new_user := NEW.user_id; END IF;
        IF TG_OP = 'DELETE' AND EXISTS (
            SELECT 1 FROM accounts_user WHERE id = OLD.user_id AND account_kind = 'staff'
        ) AND current_setting('app.account_retirement_makerspace_id', true)
                  IS DISTINCT FROM OLD.makerspace_id::text THEN
            RAISE EXCEPTION 'Staff memberships cannot be deleted outside exact-tenant purge'
                USING ERRCODE = '23514';
        END IF;
    ELSE
        IF TG_OP <> 'INSERT' THEN
            SELECT user_id INTO old_user FROM makerspaces_makerspacemembership WHERE id = OLD.membership_id;
        END IF;
        IF TG_OP <> 'DELETE' THEN
            SELECT user_id INTO new_user FROM makerspaces_makerspacemembership WHERE id = NEW.membership_id;
        END IF;
    END IF;
    -- Stable lock order also covers OLD/NEW reassignment in one statement.
    PERFORM id FROM accounts_user WHERE id IN (old_user, new_user) ORDER BY id FOR UPDATE;
    IF old_user IS NOT NULL THEN PERFORM accounts_validate_memberships(old_user); END IF;
    IF new_user IS NOT NULL AND new_user IS DISTINCT FROM old_user THEN
        PERFORM accounts_validate_memberships(new_user);
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER accounts_user_membership_valid
    AFTER INSERT OR UPDATE ON accounts_user DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION accounts_membership_constraint();
CREATE CONSTRAINT TRIGGER accounts_membership_valid
    AFTER INSERT OR UPDATE OR DELETE ON makerspaces_makerspacemembership DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION accounts_membership_constraint();
CREATE CONSTRAINT TRIGGER accounts_additional_role_valid
    AFTER INSERT OR UPDATE OR DELETE ON makerspaces_membershipadditionalrole DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION accounts_membership_constraint();
"""

REVERSE = """
DROP TRIGGER accounts_additional_role_valid ON makerspaces_membershipadditionalrole;
DROP TRIGGER accounts_membership_valid ON makerspaces_makerspacemembership;
DROP TRIGGER accounts_user_membership_valid ON accounts_user;
DROP TRIGGER accounts_user_context_immutable ON accounts_user;
DROP FUNCTION accounts_membership_constraint();
DROP FUNCTION accounts_validate_memberships(bigint);
DROP FUNCTION accounts_guard_context();
"""


class Migration(migrations.Migration):
    dependencies = [("accounts", "0032_account_context")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
