# Account split: portability and retention contract

Permanent D10/D11 and V3/V4/V5/V9/V11 contract for tenant migration and deployment
backup. See [Account kinds](INVARIANTS.md#account-kinds-member--staff--platform) for
authentication/lifecycle rules and [SOURCE-MAP.md](SOURCE-MAP.md) for implementation ownership.

PORTABLE archives and sovereign Lane D dumps carry tenant-owned staff identities,
their primary and additional built-in roles, machine-type scopes, membership
notification opt-out, legacy delivery/digest preferences and current category/channel
preferences. Staff roles resolve by protected role key to the target's seeded roles;
machine-type references follow the import map. Member memberships still reduce to
Member, and member personal delivery preferences remain source-local.

PORTABLE user rows now include `is_active`, so deactivated staff remain deactivated.
The existing `create_walk_in` identity-decision value means **create a new account**
for staff: it creates a tenant staff principal, never a walk-in member. Staff decisions
must retain membership and cannot link an existing target account. Imported staff
receive an unusable password and `must_change_password`; passwords, MFA, sessions,
device grants, endpoints and onboarding invitations do not travel. Platform actors
close historical foreign keys through inactive, PII-free stubs. The target administrator
must issue staff passwords and each chat binding must prove ownership again.

Tenant purge retires staff before deleting tenant rows. Each account is scrubbed,
disabled and disconnected from its tenant under the exact-tenant retirement guard.
Account credentials are revoked through the shared P1b service; established MFA
secrets are removed. User primary keys survive, preserving global audit actor IDs,
row MACs and batch membership. Retired shells have no exported identity.

Readable-main deployment backups retain the same PII-free staff shell shape. Full
staff rows and account-owned credential rows reside in the sealed tenant slice;
Django browser sessions are omitted operational state. Pending slices reserve source
staff usernames through an explicit supplemental broad fence, without treating the
retained User primary keys as deleted rows. The fence permits unrelated account
updates while preventing username allocation or changes until restoration.

Delayed slice restore replaces an occupied User ID only when the complete row equals
its registered shell and the active restore component owns the staff tenant. Staged
row equality, per-column inverse deltas and the database merge role independently
guard that transition. Ordinary occupied-ID inserts remain refused. The producer's
unserved reconstruction clone validates the same exact shell before applying its
inverse; its one-way trigger is disabled only around the clone's reconstruction
transaction and restored before verification. Live restoration always uses the
guarded merge role.

A chat destination can independently bind to different accounts under the same
configuration. Duplicate live binding by the same account is refused. Signed STOP,
consent renewal and inbound-window facts apply atomically to every live destination
binding; account unlink remains local and delivery statuses remain delivery-bound.
Signed opt-outs and delivery callbacks remain effective with delivery/modules off;
new proofs require the channel and notification module gates.

The export field/reference/authority catalogs classify account kind and staff ownership,
credential omissions, role/scoping remaps and staff preferences together. Import and
independent postconditions must agree; a new account edge or credential field requires
an explicit disposition before it can travel. This contract does not authorize a Space
Manager to obtain a PORTABLE global-identity archive; existing disclosure approval and
source/target migration gates still apply.
