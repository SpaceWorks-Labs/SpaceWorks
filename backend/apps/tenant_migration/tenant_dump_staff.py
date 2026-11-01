"""Frozen-image staff-track rows and target-seeded role resolution (one account per person)."""

from types import MappingProxyType

from django.apps import apps

from apps.makerspaces.role_catalog import ROLE_BY_SLUG
from .tenant_dump_errors import TenantDumpVerificationError
from .tenant_dump_raw import SanitizedRow


STAFF_CHILD_LABELS = (
    'makerspaces.MembershipAdditionalRole', 'machines.MembershipMachineTypeScope',
)


def prepare_staff_rows(rows, makerspace_id, *, using):
    """Mark staff-track rows from the immutable database, before adding user edges.

    One account per person: a staff role is a staff-track membership of a person, so the
    track -- never the account -- decides which rows carry built-in staff roles. Their
    additional roles and machine scopes travel with them; the person's notification
    choices here travel only when they hold a staff-track row (member choices stay local).
    """
    result = dict(rows)
    Role = apps.get_model('makerspaces.MakerspaceRole')
    roles = dict(Role._base_manager.using(using).filter(
        makerspace_id=makerspace_id, is_protected=True,
    ).values_list('pk', 'slug'))

    def with_role(row, field):
        slug = roles.get(row.get(field))
        if slug not in ROLE_BY_SLUG or slug == 'member':
            raise TenantDumpVerificationError('A carried staff role has no tenant built-in resolution.')
        return MappingProxyType({**row, '_staff_role_slug': slug, '_staff_account': True})

    members = []
    staff_memberships, staff_holders = set(), set()
    for row in result.get('makerspaces.MakerspaceMembership', ()):
        if row.get('track') == 'staff':
            members.append(with_role(row, 'assigned_role_id'))
            staff_memberships.add(row['id'])
            staff_holders.add(row['user_id'])
        else:
            members.append(row)
    result['makerspaces.MakerspaceMembership'] = tuple(members)
    for label in STAFF_CHILD_LABELS:
        kept = (row for row in result.get(label, ()) if row['membership_id'] in staff_memberships)
        result[label] = tuple(with_role(row, 'role_id') for row in kept) if label.endswith('MembershipAdditionalRole') else tuple(kept)
    for label in ('notifications.MemberNotificationPreference', 'notifications.NotificationPreference'):
        result[label] = tuple(row for row in result.get(label, ()) if row['user_id'] in staff_holders)
    return result


def remap_account_roles(rows, role_ids, source_rows):
    """Staff keeps its complete built-in set; every member keeps only Member."""
    primary = {
        row['id']: row['_staff_role_slug']
        for row in source_rows.get('makerspaces.MakerspaceMembership', ())
        if row.get('_staff_account')
    }
    additional = {
        row['id']: row['_staff_role_slug']
        for row in source_rows.get('makerspaces.MembershipAdditionalRole', ())
    }
    result = []
    for row in rows:
        label = row.model._meta.label
        values = dict(row.values)
        if label == 'makerspaces.MakerspaceMembership':
            slug = primary.get(row.source_pk, 'member')
            values[row.model._meta.get_field('assigned_role').column] = role_ids[slug]
            values[row.model._meta.get_field('role').column] = ROLE_BY_SLUG[slug].legacy_role or 'custom'
        elif label == 'makerspaces.MembershipRequest':
            values[row.model._meta.get_field('assigned_role').column] = role_ids['member']
        elif label == 'makerspaces.MembershipAdditionalRole':
            slug = additional.get(row.source_pk)
            if slug is None:
                raise TenantDumpVerificationError('An additional role has no staff closure entry.')
            values[row.model._meta.get_field('role').column] = role_ids[slug]
        result.append(SanitizedRow(row.model, row.source_pk, values))
    return result
