"""Global organization asset adapter; never chooses a linked tenant or its quota."""

from apps.makerspaces.public_page_assets import upload as upload_typed, delete as delete_typed


def upload(organization_id, **kwargs):
    return upload_typed("organization", organization_id, **kwargs)


def delete(organization_id, asset_id, **kwargs):
    return delete_typed("organization", organization_id, asset_id, **kwargs)
