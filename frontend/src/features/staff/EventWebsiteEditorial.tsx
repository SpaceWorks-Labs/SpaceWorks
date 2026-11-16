import { t } from "@lingui/core/macro";
import type { EventWebsite, WebsiteTarget } from "../events/websiteTypes";
import { eventEditorialTypes } from "../events/websiteSectionRegistry";
import { PagePresentationForm, pagePaletteChoices } from "../publicPages/PagePresentationForm";
import { PageSectionsEditor } from "../publicPages/PageSectionsEditor";

export function EventWebsiteEditorial({ page, target, disabled, onChange }: {
  page: EventWebsite; target: WebsiteTarget; disabled: boolean; onChange: (page: EventWebsite) => void;
}) {
  const document = page.editorial_document;
  const caps = page.capabilities;
  if (!document || !caps) return null;
  const assets = (page.assets ?? []).map(asset => ({ ...asset, pinned: asset.pinned ?? false, preview_url: `/api/v1/admin/${target.kind}/${target.id}/website/assets/${asset.id}` }));
  return <section aria-label={t`Event editorial content`} className="grid gap-5">
    <h3 className="title-section">{t`Editorial content`}</h3>
    <PagePresentationForm document={document} assets={assets} choices={pagePaletteChoices} disabled={disabled || !caps.can_edit_details} onChange={editorial_document => onChange({ ...page, editorial_document })} />
    <PageSectionsEditor document={document} assets={assets} allowed={[...eventEditorialTypes]} required={[]} kind="event" disabled={disabled || !caps.can_edit_details} onChange={editorial_document => onChange({ ...page, editorial_document })} />
  </section>;
}
