from apps.accounts.rbac_roles import additional_roles_prefetch
from apps.accounts.rbac_roles import membership_roles
from apps.integrations.models_recipients import NotificationRecipientKind
from apps.integrations.recipient_scope_matching import rule_covers as _rule_covers
from apps.integrations.recipients_object_scope import person_object_filter
from apps.integrations.recipients_selection import logger, selection_rows


def _eligible_memberships(makerspace):
    """Active, notifiable memberships of this makerspace.

    `receives_notifications` is filtered in the QUERY, not in Python: it is the member's
    own opt-out (D5) and it outranks a staff selection, so no branch below can bypass it
    by forgetting the check.
    """
    from apps.accounts.models import User
    from apps.makerspaces.models import MakerspaceMembership

    # Both tracks: role and action selections reach staff rows, member selections
    # community rows; addresses are de-duplicated downstream.
    return (
        MakerspaceMembership.both_tracks().filter(
            makerspace=makerspace,
            status="active",
            receives_notifications=True,
            user__is_active=True,
            user__access_status=User.AccessStatus.ACTIVE,
        )
        .exclude(user__is_superuser=True)
        .exclude(user__role=User.Role.SUPERADMIN)
        .select_related("user", "assigned_role").prefetch_related(additional_roles_prefetch())
        .order_by("id")
    )


def _role_scope_admits(membership_scopes, membership, scope) -> bool:
    """Whether a role-selected recipient's machine reach covers this alert's machine.

    D9's floor for `kind=role` rows: "does this role's MANAGE_MACHINES grant reach this
    machine". People selected by name or as all members get the same floor through
    `recipients_object_scope.person_object_filter` (owner decision #75c), which also
    admits type managers and machine operators, since a person may see a machine through
    either without holding the role grant.
    """
    if scope is None or (scope.machine_id is None and scope.machine_type_id is None):
        return True
    from apps.machines import role_scope as machine_role_scope

    resolved = membership_scopes.get(membership.pk, machine_role_scope.NOTHING)
    if resolved is machine_role_scope.EXEMPT:
        return True
    type_ids, machine_ids = resolved
    return scope.machine_type_id in type_ids or (scope.machine_id is not None and scope.machine_id in machine_ids)


def reach_filter_for(memberships, scope):
    """A predicate saying whether each membership's machine reach admits this alert.

    Used by the ACTION-BASED FALLBACK, not by an explicit selection. The fallback sends to
    every membership holding the feature's action, which predates machine scoping and is
    makerspace-wide -- so once an alert names a machine, it would mail a laser-only
    maintainer the printer's maintenance detail for a machine they cannot even open in the
    console. Scoping the fallback keeps it consistent with the rest of the program.

    **A ROLE WITH NO LINKS STILL RECEIVES THE FALLBACK, and that asymmetry is the whole
    point.** For ACCESS, no links means reach nothing — machine scoping fails closed. Here
    it must mean the opposite: a role that was never given links has not been narrowed, it
    has simply never been configured, and treating that as "reaches no machine" would mute
    a space's maintenance mail the moment an alert named a machine. That is precisely the
    failure this module forbids, so the filter only ever removes a membership whose role
    holds links that genuinely exclude the subject.

    Exempt actors (a space manager, a null-`assigned_role` legacy membership) always admit,
    so a machine nobody is scoped to still reaches whoever administers the space. Alerts
    naming no machine admit everyone, leaving every non-machine feature untouched.
    """
    from apps.machines import role_scope as machine_role_scope

    memberships = list(memberships)
    if scope is None or (scope.machine_id is None and scope.machine_type_id is None):
        return lambda membership: True
    scopes = machine_role_scope.manage_scopes_for_memberships(memberships)

    def admits(membership):
        resolved = scopes.get(membership.pk, machine_role_scope.EXEMPT)
        if resolved is machine_role_scope.EXEMPT:
            return True
        type_ids, machine_ids = resolved
        if not type_ids and not machine_ids:
            # Unconfigured, not narrowed -- fail open.
            return True
        return scope.machine_type_id in type_ids or (scope.machine_id is not None and scope.machine_id in machine_ids)

    return admits


def _selected_memberships(makerspace, rows, scope=None):
    """Memberships matched by a selection, in a stable order.

    Every kind resolves through a MEMBERSHIP of this makerspace — including `user`
    (D4). A notification body carries requester names, machine detail and booking info;
    addressing it to an arbitrary platform account is a hand-operated data leak, and on
    managed hosting it crosses tenants. An external contractor gets a no-action Member
    role first. The role FK is matched by id under a makerspace-scoped queryset, so a
    row pointing at another space's role is inert rather than a leak.

    Composition is `object_scope AND (rule_scope OR all)` (D9) for EVERY kind (#75c) —
    narrowing only, never widening, so a recipient can never be alerted about a machine
    they would 403 on, whether they were selected as a role or as a person.
    """
    # Coverage first, precedence second -- see the comment in the loop below.
    rows = [row for row in rows if _rule_covers(row, scope)]
    role_rows = {row.role_id: row for row in rows if row.role_id}
    user_rows = {row.user_id: row for row in rows if row.user_id}
    member_rows = [row for row in rows if row.kind == NotificationRecipientKind.MEMBERS]
    if not (role_rows or user_rows or member_rows):
        return []

    candidates = []
    for membership in _eligible_memberships(makerspace):
        # One row is responsible for each membership's inclusion, and it is the one whose
        # narrowing applies. Members-wide is checked first so a broad tick is not
        # accidentally narrowed by an unrelated per-role rule.
        #
        # Precedence is applied ONLY among rows that already cover this subject, because
        # the rows were filtered above. Choosing a row first and testing coverage after
        # let a broad-but-irrelevant row shadow a narrow relevant one: a members row
        # scoped to the printers would be picked for a laser alert, fail coverage, and
        # skip the membership entirely -- so the laser-scoped role row that *does* cover
        # it was never consulted and the alert reached nobody. That is the same
        # suppression `has_selection` was fixed for, one level further down, and 6c2 makes
        # the combination ordinary: a delegated laser rule sits beside a preserved
        # space-wide members rule by design.
        row = None
        if member_rows:
            row = member_rows[0]
        elif any(role.pk in role_rows for role in membership_roles(membership)):
            row = next(role_rows[role.pk] for role in membership_roles(membership)
                       if role.pk in role_rows)
        elif membership.user_id in user_rows:
            row = user_rows[membership.user_id]
        if row is None:
            continue
        candidates.append((membership, row))

    if not candidates:
        return []

    from apps.machines import role_scope as machine_role_scope

    role_selected = [
        membership
        for membership, row in candidates
        if row.kind == NotificationRecipientKind.ROLE
    ]
    membership_scopes = (
        machine_role_scope.manage_scopes_for_memberships(role_selected)
        if role_selected
        else {}
    )
    feature = rows[0].feature
    # A room-scoped booking alert judges role recipients by the same "may see this room"
    # rule as named people (owner decision #91); every other role keeps its reach floor.
    rooms = feature == "bookings"
    person_sees = person_object_filter(
        [membership for membership, row in candidates
         if rooms or row.kind != NotificationRecipientKind.ROLE],
        scope,
        feature=feature,
    )
    return [
        membership
        for membership, row in candidates
        if (_role_scope_admits(membership_scopes, membership, scope)
            if row.kind == NotificationRecipientKind.ROLE and not rooms else person_sees(membership))
    ]


def selected_emails(makerspace, feature, event, scope=None) -> list[str]:
    """Addresses for an explicit selection. Assumes has_selection() is True."""
    rows = selection_rows(makerspace, feature, event)
    if not rows:
        return []
    try:
        emails, seen = [], set()
        for membership in _selected_memberships(makerspace, rows, scope):
            email = (membership.user.email or "").strip()
            if not email:
                continue
            normalized = email.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            emails.append(email)
        return emails
    except Exception:
        logger.warning(
            "notification_selected_recipient_resolution_failed",
            extra={"makerspace_id": getattr(makerspace, "pk", None), "feature": feature},
            exc_info=True,
        )
        return []


def selected_user_ids(makerspace, feature, event, scope=None) -> list[int]:
    """Push recipients for an explicit selection.

    Native push is a MEMBER channel as well as a staff one (D8) — the mobile form of the
    member's own email — so it is filtered by exactly the same selection and opt-out as
    email rather than by a separate matrix.
    """
    rows = selection_rows(makerspace, feature, event)
    if not rows:
        return []
    try:
        return list(
            dict.fromkeys(
                membership.user_id
                for membership in _selected_memberships(makerspace, rows, scope)
            )
        )
    except Exception:
        logger.warning(
            "notification_selected_push_resolution_failed",
            extra={"makerspace_id": getattr(makerspace, "pk", None), "feature": feature},
            exc_info=True,
        )
        return []
