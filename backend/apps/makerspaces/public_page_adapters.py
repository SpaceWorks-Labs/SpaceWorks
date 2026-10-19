"""Explicit typed adapters. Optional event/inventory apps are never imported here."""

from dataclasses import dataclass
from . import models_public_pages as maker
from .public_page_authority import (lock_local_manager, lock_organization_governor, read_local_manager,
                                    read_organization_governor)


@dataclass(frozen=True)
class PageAdapter:
    kind: str
    page: type
    revision: type
    asset: type
    asset_reference: type
    member_reference: type
    lock_owner: object
    read_owner: object

    def lookup(self, owner):
        return {f"{self.kind}_id": owner.pk}


def adapter(kind):
    if kind == "makerspace":
        return PageAdapter(kind, maker.MakerspacePublicPage, maker.MakerspacePublicPageRevision,
                           maker.MakerspacePublicPageAsset, maker.MakerspacePublicPageRevisionAsset,
                           maker.MakerspacePublicPageRevisionMember, lock_local_manager, read_local_manager)
    if kind == "organization":
        from apps.organizations import models_public_pages as org
        return PageAdapter(kind, org.OrganizationPublicPage, org.OrganizationPublicPageRevision,
                           org.OrganizationPublicPageAsset, org.OrganizationPublicPageRevisionAsset,
                           org.OrganizationPublicPageRevisionMember, lock_organization_governor,
                           read_organization_governor)
    raise ValueError("Unsupported page owner.")
