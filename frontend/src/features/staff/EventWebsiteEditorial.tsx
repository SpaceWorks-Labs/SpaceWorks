import type { EventWebsite, WebsiteTarget } from "../events/websiteTypes";
import { eventEditorialTypes } from "../events/websiteSectionRegistry";
import { PagePresentationForm } from "../publicPages/PagePresentationForm";
import { PageSectionsEditor } from "../publicPages/PageSectionsEditor";

export function EventWebsiteEditorial({ page, target, disabled, onChange }: {
  page: EventWebsite; target: WebsiteTarget; disabled: boolean; onChange: (page: EventWebsite) => void;
}) {
  const document = page.editorial_document;
  const caps = page.capabilities;
  if (!document || !caps) return null;
  const assets = (page.assets ?? []).map(asset => ({ ...asset, pinned: asset.pinned ?? false, preview_url: `/api/v1/admin/${target.kind}/${target.id}/website/assets/${asset.id}` }));
  return <section aria-label="Event editorial content" className="grid gap-5">
    <h3 className="title-section">Editorial content</h3>
    <PagePresentationForm document={document} assets={assets} choices={caps.palette_choices} disabled={disabled || !caps.can_edit_details} onChange={editorial_document => onChange({ ...page, editorial_document })} />
    <PageSectionsEditor document={document} assets={assets} allowed={caps.allowed_section_types.filter(type => (eventEditorialTypes as readonly string[]).includes(type))} required={caps.required_groups} kind="event" disabled={disabled || !caps.can_edit_details} onChange={editorial_document => onChange({ ...page, editorial_document })} />
  </section>;
}
