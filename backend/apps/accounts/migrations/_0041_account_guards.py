"""Frozen SQL for the account/native reconciliation forward migration."""

SQL = r"""
CREATE FUNCTION accounts_guard_device_context() RETURNS trigger LANGUAGE plpgsql AS $$
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
    IF principal.id IS NULL OR principal.account_kind NOT IN ('member', 'staff')
       OR NEW.authority <> principal.account_kind OR NOT principal.is_active
       OR principal.retired_at IS NOT NULL OR principal.is_tenant_dump_stub
       OR principal.deletion_requested_at IS NOT NULL OR principal.access_status <> 'active'
       OR NEW.credential_generation <> principal.credential_generation
       OR NEW.staff_makerspace_id IS DISTINCT FROM principal.staff_makerspace_id
       OR registration.id IS NULL OR registration.status <> 'approved'
       OR ROW(NEW.platform, NEW.app_id, NEW.environment)
          IS DISTINCT FROM ROW(registration.platform, registration.app_id, registration.environment) THEN
        RAISE EXCEPTION 'Device account context mismatch' USING ERRCODE = '23514';
    END IF;
    IF principal.account_kind = 'staff' AND (
       NEW.login_method <> 'password' OR NEW.signing_identity = ''
       OR NEW.attestation_subject_fingerprint = ''
       OR registration.makerspace_id IS NOT NULL
          AND registration.makerspace_id <> principal.staff_makerspace_id
       OR NOT EXISTS (SELECT 1 FROM accounts_usermfa WHERE user_id = principal.id AND enabled_at IS NOT NULL)
    ) THEN
        RAISE EXCEPTION 'Native staff requires fixed tenant, password, MFA and attestation'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER accounts_device_context BEFORE INSERT OR UPDATE ON accounts_devicegrant
    FOR EACH ROW EXECUTE FUNCTION accounts_guard_device_context();

CREATE FUNCTION accounts_guard_device_family() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND ROW(NEW.user_id, NEW.grant_id) IS DISTINCT FROM ROW(OLD.user_id, OLD.grant_id) THEN
        RAISE EXCEPTION 'Device family ownership is immutable' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS NULL THEN
        RAISE EXCEPTION 'Device family revocation is permanent' USING ERRCODE = '23514';
    END IF;
    IF NEW.revoked_at IS NULL AND NOT EXISTS (
        SELECT 1 FROM accounts_devicegrant WHERE id = NEW.grant_id AND user_id = NEW.user_id
    ) THEN
        RAISE EXCEPTION 'Device family owner mismatch' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER accounts_device_family_owner BEFORE INSERT OR UPDATE ON accounts_devicerefreshfamily
    FOR EACH ROW EXECUTE FUNCTION accounts_guard_device_family();

CREATE FUNCTION accounts_guard_recovery_context() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE principal accounts_user%ROWTYPE;
BEGIN
    IF TG_OP = 'UPDATE' AND ROW(NEW.user_id, NEW.context, NEW.makerspace_id)
        IS DISTINCT FROM ROW(OLD.user_id, OLD.context, OLD.makerspace_id) THEN
        RAISE EXCEPTION 'Recovery ownership is immutable' USING ERRCODE = '23514';
    END IF;
    SELECT * INTO principal FROM accounts_user WHERE id = NEW.user_id;
    IF principal.id IS NULL OR NEW.context <> principal.account_kind
       OR NEW.makerspace_id IS DISTINCT FROM principal.staff_makerspace_id THEN
        RAISE EXCEPTION 'Recovery account context mismatch' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER accounts_recovery_context BEFORE INSERT OR UPDATE ON accounts_passwordresetenvelope
    FOR EACH ROW EXECUTE FUNCTION accounts_guard_recovery_context();

CREATE FUNCTION accounts_guard_member_credential() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_id bigint;
BEGIN
    IF TG_TABLE_NAME = 'accounts_applerefreshcredential' THEN
        SELECT user_id INTO owner_id FROM accounts_socialidentity WHERE id = (to_jsonb(NEW)->>'social_identity_id')::bigint;
    ELSE
        owner_id := (to_jsonb(NEW)->>'user_id')::bigint;
    END IF;
    IF owner_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM accounts_user WHERE id = owner_id AND account_kind = 'member'
    ) THEN
        RAISE EXCEPTION 'Member-only credential or lifecycle work' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
"""

MEMBER_TABLES = (
    "accountpurgeprogress", "accountpurgeobject", "applerefreshcredential", "applerevocation",
    "accountrestoreintent",
)
SQL += "\n".join(
    f"CREATE TRIGGER accounts_{table}_member BEFORE INSERT OR UPDATE ON accounts_{table} "
    "FOR EACH ROW EXECUTE FUNCTION accounts_guard_member_credential();"
    for table in MEMBER_TABLES
)

REVERSE = "\n".join(
    f"DROP TRIGGER accounts_{table}_member ON accounts_{table};" for table in MEMBER_TABLES
) + """
DROP TRIGGER accounts_recovery_context ON accounts_passwordresetenvelope;
DROP TRIGGER accounts_device_family_owner ON accounts_devicerefreshfamily;
DROP TRIGGER accounts_device_context ON accounts_devicegrant;
DROP FUNCTION accounts_guard_member_credential();
DROP FUNCTION accounts_guard_recovery_context();
DROP FUNCTION accounts_guard_device_family();
DROP FUNCTION accounts_guard_device_context();
"""
