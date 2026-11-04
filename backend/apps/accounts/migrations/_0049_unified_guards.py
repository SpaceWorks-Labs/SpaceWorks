"""Frozen SQL for the unified-accounts schema migration (accounts 0049).

GUCs (transaction-local, set only by their owning service):
- ``app.account_unification_run_id``: staff->person conversion (migration 0050) and
  person->merged-shell (the merge engine).
- ``app.account_shell_import_job_id``: the EXACT running tenant import that may insert an
  inert shell or remap ``merged_into``.
- ``app.tenant_purge_makerspace_id`` (and the legacy ``app.account_retirement_makerspace_id``):
  exact-tenant purge, the only path that deletes staff-track rows.
- ``app.account_purge_user_id``: the account purge scrubbing a completed merge record's
  PII snapshot.
"""

_IMPORTING = r"""
    IF COALESCE(shell_import, '') <> '' AND to_regclass('tenant_migration_tenantimportjob') IS NOT NULL THEN
        EXECUTE 'SELECT EXISTS (SELECT 1 FROM tenant_migration_tenantimportjob '
                'WHERE id::text = $1 AND status = ANY($2))'
            INTO importing USING shell_import, ARRAY['materializing', 'finalizing'];
    END IF;
"""

GUARD_CONTEXT = r"""
CREATE OR REPLACE FUNCTION accounts_guard_context() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    unification text := current_setting('app.account_unification_run_id', true);
    shell_import text := current_setting('app.account_shell_import_job_id', true);
    importing boolean := false;
BEGIN
""" + _IMPORTING + r"""
    IF TG_OP = 'DELETE' THEN
        IF OLD.account_kind = 'staff' OR OLD.merged_into_id IS NOT NULL THEN
            RAISE EXCEPTION 'Inert shells are retained, never deleted' USING ERRCODE = '23514';
        END IF;
        RETURN OLD;
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.account_kind = 'staff' OR NEW.merged_into_id IS NOT NULL THEN
            IF NOT importing THEN
                RAISE EXCEPTION 'Inert shells are created only by an exact tenant import'
                    USING ERRCODE = '23514';
            END IF;
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.account_kind = 'staff' AND NEW.account_kind = 'member' THEN
        IF COALESCE(unification, '') = '' OR OLD.retired_at IS NOT NULL OR OLD.merged_into_id IS NOT NULL
           OR OLD.staff_makerspace_id IS NULL OR NEW.staff_makerspace_id IS NOT NULL
           OR NEW.retired_at IS NOT NULL OR NEW.merged_into_id IS NOT NULL THEN
            RAISE EXCEPTION 'Staff accounts become people only in the unification run'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.account_kind = 'member' AND NEW.account_kind = 'staff' THEN
        IF COALESCE(unification, '') = '' OR OLD.merged_into_id IS NOT NULL
           OR NEW.merged_into_id IS NULL OR NEW.merged_at IS NULL OR NEW.is_active
           OR NEW.staff_makerspace_id IS NOT NULL OR NEW.retired_at IS NOT NULL THEN
            RAISE EXCEPTION 'A person becomes a merged shell only in a unification run'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.account_kind IS DISTINCT FROM OLD.account_kind THEN
        RAISE EXCEPTION 'Account kind is immutable' USING ERRCODE = '23514';
    END IF;
    IF NEW.merged_into_id IS DISTINCT FROM OLD.merged_into_id
       OR NEW.merged_at IS DISTINCT FROM OLD.merged_at THEN
        IF NOT importing OR OLD.merged_into_id IS NULL OR NEW.merged_into_id IS NULL THEN
            RAISE EXCEPTION 'A merged shell is remapped only by an exact tenant import'
                USING ERRCODE = '23514';
        END IF;
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
DROP TRIGGER accounts_user_context_immutable ON accounts_user;
CREATE TRIGGER accounts_user_context_immutable BEFORE INSERT OR UPDATE OR DELETE ON accounts_user
    FOR EACH ROW EXECUTE FUNCTION accounts_guard_context();
"""

VALIDATE_MEMBERSHIPS = r"""
CREATE OR REPLACE FUNCTION accounts_validate_memberships(subject_id bigint) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    subject accounts_user%ROWTYPE;
    membership makerspaces_makerspacemembership%ROWTYPE;
    primary_role makerspaces_makerspacerole%ROWTYPE;
BEGIN
    SELECT * INTO subject FROM accounts_user WHERE id = subject_id FOR UPDATE;
    IF NOT FOUND THEN RETURN; END IF;
    IF subject.account_kind <> 'member' OR subject.retired_at IS NOT NULL OR subject.merged_into_id IS NOT NULL THEN
        -- A merged shell keeps only REVOKED rows the merge left behind (unique-resolve
        -- losers); platform accounts and retired shells hold none.
        IF EXISTS (SELECT 1 FROM makerspaces_makerspacemembership WHERE user_id = subject_id
                   AND (subject.merged_into_id IS NULL OR status <> 'revoked')) THEN
            RAISE EXCEPTION 'Platform accounts and inert shells hold no live memberships'
                USING ERRCODE = '23514';
        END IF;
        RETURN;
    END IF;
    FOR membership IN SELECT * FROM makerspaces_makerspacemembership WHERE user_id = subject_id LOOP
        SELECT * INTO primary_role FROM makerspaces_makerspacerole WHERE id = membership.assigned_role_id;
        IF NOT FOUND OR primary_role.makerspace_id <> membership.makerspace_id
            OR NOT primary_role.is_default OR NOT primary_role.is_protected
            OR membership.status NOT IN ('active', 'revoked')
            OR membership.track NOT IN ('community', 'staff') THEN
            RAISE EXCEPTION 'Membership requires a same-tenant built-in role and valid status'
                USING ERRCODE = '23514';
        END IF;
        -- Keyed on role properties, not a slug list, so later built-in staff roles
        -- (Technician, Shop Manager) need no trigger rewrite: any built-in role but
        -- Member is a staff role, and every one but Space Manager combines.
        IF membership.track = 'staff' AND primary_role.slug = 'member' THEN
            RAISE EXCEPTION 'Staff-track rows hold only built-in staff roles' USING ERRCODE = '23514';
        ELSIF membership.track = 'community' AND primary_role.slug <> 'member' THEN
            RAISE EXCEPTION 'Community rows hold only the Member role' USING ERRCODE = '23514';
        END IF;
        IF EXISTS (
            SELECT 1 FROM makerspaces_membershipadditionalrole link
            JOIN makerspaces_makerspacerole role ON role.id = link.role_id
            WHERE link.membership_id = membership.id AND (
                membership.track <> 'staff' OR primary_role.slug = 'space_manager'
                OR role.makerspace_id <> membership.makerspace_id
                OR NOT role.is_default OR NOT role.is_protected
                OR role.slug IN ('member', 'space_manager')
                OR role.id = primary_role.id
            )
        ) THEN
            RAISE EXCEPTION 'Invalid additional membership role' USING ERRCODE = '23514';
        END IF;
    END LOOP;
END $$;
"""

MEMBERSHIP_CONSTRAINT = r"""
CREATE OR REPLACE FUNCTION accounts_membership_constraint() RETURNS trigger LANGUAGE plpgsql AS $$
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
        IF TG_OP = 'DELETE' AND OLD.track = 'staff'
           AND current_setting('app.tenant_purge_makerspace_id', true)
               IS DISTINCT FROM OLD.makerspace_id::text
           AND current_setting('app.account_retirement_makerspace_id', true)
               IS DISTINCT FROM OLD.makerspace_id::text THEN
            RAISE EXCEPTION 'Staff-track memberships are revoked, never deleted, outside exact-tenant purge'
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
"""

DEVICE_CONTEXT = r"""
CREATE OR REPLACE FUNCTION accounts_guard_device_context() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    principal accounts_user%ROWTYPE;
    registration accounts_nativeappregistration%ROWTYPE;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF ROW(NEW.user_id, NEW.registration_id, NEW.authority, NEW.staff_makerspace_id,
               NEW.credential_generation, NEW.login_method, NEW.platform, NEW.app_id,
               NEW.environment, NEW.signing_identity, NEW.attestation_subject_fingerprint,
               NEW.attestation_key_id, NEW.attestation_public_key, NEW.attested_at)
           IS DISTINCT FROM
           ROW(OLD.user_id, OLD.registration_id, OLD.authority, OLD.staff_makerspace_id,
               OLD.credential_generation, OLD.login_method, OLD.platform, OLD.app_id,
               OLD.environment, OLD.signing_identity, OLD.attestation_subject_fingerprint,
               OLD.attestation_key_id, OLD.attestation_public_key, OLD.attested_at) THEN
            RAISE EXCEPTION 'Device provenance is immutable' USING ERRCODE = '23514';
        END IF;
        IF (OLD.status = 'revoked' OR OLD.revoked_at IS NOT NULL)
            AND NEW.status = 'active' AND NEW.revoked_at IS NULL THEN
            RAISE EXCEPTION 'Revoked device authority cannot be restored' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NEW.status = 'revoked' OR NEW.revoked_at IS NOT NULL THEN RETURN NEW; END IF;
    SELECT * INTO principal FROM accounts_user WHERE id = NEW.user_id FOR NO KEY UPDATE;
    SELECT * INTO registration FROM accounts_nativeappregistration WHERE id = NEW.registration_id;
    IF principal.id IS NULL OR principal.account_kind <> 'member'
       OR NEW.authority NOT IN ('member', 'staff') OR NOT principal.is_active
       OR principal.retired_at IS NOT NULL OR principal.merged_into_id IS NOT NULL
       OR principal.is_tenant_dump_stub
       OR principal.deletion_requested_at IS NOT NULL OR principal.access_status <> 'active'
       OR NEW.credential_generation <> principal.credential_generation
       OR (NEW.authority = 'member') <> (NEW.staff_makerspace_id IS NULL)
       OR registration.id IS NULL OR registration.status <> 'approved'
       OR ROW(NEW.platform, NEW.app_id, NEW.environment)
          IS DISTINCT FROM ROW(registration.platform, registration.app_id, registration.environment) THEN
        RAISE EXCEPTION 'Device account context mismatch' USING ERRCODE = '23514';
    END IF;
    -- A staff grant is a step-up on a person: one fixed tenant where the person holds an
    -- active staff-track row, an enabled factor and attestation; any primary login method.
    IF NEW.authority = 'staff' AND (
       NEW.signing_identity = '' OR NEW.attestation_subject_fingerprint = ''
       OR registration.makerspace_id IS NOT NULL
          AND registration.makerspace_id <> NEW.staff_makerspace_id
       OR NOT EXISTS (SELECT 1 FROM makerspaces_makerspacemembership
                      WHERE user_id = principal.id AND makerspace_id = NEW.staff_makerspace_id
                        AND track = 'staff' AND status = 'active')
       OR NOT EXISTS (SELECT 1 FROM accounts_usermfa WHERE user_id = principal.id AND enabled_at IS NOT NULL)
    ) THEN
        RAISE EXCEPTION 'Native staff authority requires a staff role in its fixed tenant, a factor and attestation'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
"""

RECOVERY_CONTEXT = r"""
CREATE OR REPLACE FUNCTION accounts_guard_recovery_context() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE principal accounts_user%ROWTYPE;
BEGIN
    IF TG_OP = 'UPDATE' AND ROW(NEW.user_id, NEW.context, NEW.makerspace_id)
        IS DISTINCT FROM ROW(OLD.user_id, OLD.context, OLD.makerspace_id) THEN
        RAISE EXCEPTION 'Recovery ownership is immutable' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.context NOT IN ('member', 'platform') THEN
        -- A legacy staff-context envelope may only be retired.
        IF NEW.digest_is_live OR NEW.status NOT IN ('consumed', 'discarded', 'undeliverable', 'delivery_unknown') THEN
            RAISE EXCEPTION 'Legacy staff recovery envelopes can only be discarded' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    SELECT * INTO principal FROM accounts_user WHERE id = NEW.user_id;
    IF principal.id IS NULL OR NEW.context NOT IN ('member', 'platform')
       OR NEW.context <> principal.account_kind OR NEW.makerspace_id IS NOT NULL THEN
        RAISE EXCEPTION 'Recovery account context mismatch' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
"""

MERGE_RECORD = r"""
CREATE FUNCTION accounts_guard_merge_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Account merge records are append-only' USING ERRCODE = '23514';
    END IF;
    IF ROW(NEW.id, NEW.decision, NEW.source_id, NEW.target_id, NEW.proof_method, NEW.run_id, NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.id, OLD.decision, OLD.source_id, OLD.target_id, OLD.proof_method, OLD.run_id, OLD.created_at) THEN
        RAISE EXCEPTION 'Account merge record identity is immutable' USING ERRCODE = '23514';
    END IF;
    IF OLD.state = 'completed' THEN
        -- The one permitted write: the account purge scrubbing the PII snapshot.
        IF NEW.snapshot_scheme = 'scrubbed' AND NEW.snapshot_ciphertext = ''
           AND NEW.snapshot_key_version IS NULL
           AND ROW(NEW.plan_sha256, NEW.held_fields, NEW.roles_kept, NEW.counts, NEW.state, NEW.completed_at)
               IS NOT DISTINCT FROM
               ROW(OLD.plan_sha256, OLD.held_fields, OLD.roles_kept, OLD.counts, OLD.state, OLD.completed_at)
           AND current_setting('app.account_purge_user_id', true) IN (OLD.source_id::text, OLD.target_id::text) THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Completed account merge records are immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER accounts_merge_record_append_only BEFORE UPDATE OR DELETE ON accounts_accountmergerecord
    FOR EACH ROW EXECUTE FUNCTION accounts_guard_merge_record();
"""

SQL = GUARD_CONTEXT + VALIDATE_MEMBERSHIPS + MEMBERSHIP_CONSTRAINT + DEVICE_CONTEXT + RECOVERY_CONTEXT + MERGE_RECORD


def _between(text, start, end):
    head = text.index(start)
    return text[head:text.index(end, head)]


def reverse_sql():
    """The pre-0049 bodies, read from the migrations that installed them (0048
    restored the 0033 ``accounts_guard_context`` body)."""
    from importlib import import_module

    context = import_module("apps.accounts.migrations.0033_account_context_triggers").SQL
    from ._0041_account_guards import SQL as native

    def replaceable(body):
        return body.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)

    return "\n".join((
        "DROP TRIGGER accounts_merge_record_append_only ON accounts_accountmergerecord;",
        "DROP FUNCTION accounts_guard_merge_record();",
        "DROP TRIGGER accounts_user_context_immutable ON accounts_user;",
        "CREATE TRIGGER accounts_user_context_immutable BEFORE UPDATE OR DELETE ON accounts_user "
        "FOR EACH ROW EXECUTE FUNCTION accounts_guard_context();",
        replaceable(_between(context, "CREATE FUNCTION accounts_guard_context",
                             "CREATE TRIGGER accounts_user_context_immutable")),
        replaceable(_between(context, "CREATE FUNCTION accounts_validate_memberships",
                             "CREATE FUNCTION accounts_membership_constraint")),
        replaceable(_between(context, "CREATE FUNCTION accounts_membership_constraint",
                             "CREATE CONSTRAINT TRIGGER")),
        replaceable(_between(native, "CREATE FUNCTION accounts_guard_device_context",
                             "CREATE TRIGGER accounts_device_context")),
        replaceable(_between(native, "CREATE FUNCTION accounts_guard_recovery_context",
                             "CREATE TRIGGER accounts_recovery_context")),
    ))
