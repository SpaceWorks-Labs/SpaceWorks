"""Read only pre-0088 columns, for both historical migrations and the preview."""


PRE_SCHEMA_FIELDS = {
    "makerspaces.Makerspace": "id name slug",
    "makerspaces.MakerspaceRole":
        "id makerspace_id name slug legacy_role granted_actions is_default is_protected",
    "makerspaces.MakerspaceMembership": "id makerspace_id user_id status assigned_role_id role",
    "makerspaces.MembershipRequest": "id makerspace_id state assigned_role_id",
    "accounts.StaffInvitation":
        "id makerspace_id role_id granted_actions expires_at accepted_at revoked_at failed_attempts",
    "integrations.NotificationRecipient": "id makerspace_id feature event kind role_id",
    "operations.ReportSchedule":
        "id makerspace_id recipient_roles recipient_actions recipient_emails destination_id is_active",
    "machines.MachineType": "id makerspace_id",
    "machines.Machine": "id makerspace_id",
    "integrations.RecipientMachineTypeScope": "id recipient_id machine_type_id",
    "integrations.RecipientMachineScope": "id recipient_id machine_id",
    "integrations.RecipientCategoryScope": "id recipient_id category_id",
}


def read_snapshot(models, connection, makerspace_id=None):
    """Never select new columns/tables or resolve effective runtime authority.

    Role/type/link rows are read across tenants so foreign references can be
    classified accurately even when previewing just one makerspace.
    """
    alias = connection.alias
    snapshot = {}
    for label, fields in PRE_SCHEMA_FIELDS.items():
        # _base_manager: the live MakerspaceMembership.objects filters on `track`, a column the
        # pre-0088 schema the preview reads does not have (decision 63 added it later).
        query = models[label]._base_manager.using(alias).order_by("id")
        if makerspace_id is not None:
            if label == "makerspaces.Makerspace":
                query = query.filter(pk=makerspace_id)
            elif label in {
                "makerspaces.MakerspaceMembership", "makerspaces.MembershipRequest",
                "accounts.StaffInvitation", "integrations.NotificationRecipient",
                "operations.ReportSchedule",
            }:
                query = query.filter(makerspace_id=makerspace_id)
        snapshot[label] = list(query.values(*fields.split()))

    # These old tables may outlive their model classes. Identifiers are fixed
    # constants, quoted with the backend API; no user input enters SQL.
    with connection.cursor() as cursor:
        for table, column, key in (
            ("machines_rolemachinetypescope", "machine_type_id", "role_type_links"),
            ("machines_rolemachinescope", "machine_id", "role_machine_links"),
        ):
            quote = connection.ops.quote_name
            cursor.execute(
                f"SELECT {quote('role_id')}, {quote(column)} FROM {quote(table)} "
                f"ORDER BY {quote('role_id')}, {quote(column)}"
            )
            snapshot[key] = list(cursor.fetchall())
    return snapshot
