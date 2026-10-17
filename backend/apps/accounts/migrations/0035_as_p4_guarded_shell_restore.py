"""Permit only the owning B1 merge role to reverse a registered staff shell."""
from django.db import migrations

SQL = r"""
CREATE OR REPLACE FUNCTION accounts_guard_context() RETURNS trigger LANGUAGE plpgsql AS $$
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
        IF current_user = 'spaceworks_b1_merge' THEN
            IF public.backup_b1_staff_shell_restore(to_jsonb(OLD), to_jsonb(NEW)) THEN
                RETURN NEW;
            END IF;
        END IF;
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
"""
REVERSE = r"""
CREATE OR REPLACE FUNCTION accounts_guard_context() RETURNS trigger LANGUAGE plpgsql AS $$
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
"""

class Migration(migrations.Migration):
    dependencies = [("accounts", "0034_staff_invitation_account"), ("backup", "0019_b1_delayed_slice_merge")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
