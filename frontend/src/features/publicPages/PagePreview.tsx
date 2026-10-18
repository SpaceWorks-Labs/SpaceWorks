import { PageImage } from "./PageImage";
import { PublicPageSections } from "./PublicPageSections";
import { usePageBranding } from "./usePageBranding";
import type { PreviewProjection } from "./pageTypes";
import { SocialCardPreview } from "./SocialCardPreview";

/** A region, rather than another page layout, keeps preview landmarks out of the console shell. */
export function PagePreview({ page }: { page: PreviewProjection }) {
  const style = usePageBranding(page.presentation.resolved_theme, page.presentation.accent_choice);
  return <div role="region" aria-label="Validated draft preview" style={style} className="grid min-w-0 gap-5 rounded-xl border border-dashed border-line bg-bg p-5 text-ink">
    <p className="eyebrow">Draft preview · not published</p><h3 className="title-panel">{page.title}</h3><p className="text-muted">{page.description}</p>
    {page.cover ? <PageImage url={page.cover.url} alt={page.cover.alt} token={page.publication_token} privatePreview /> : null}
    <PublicPageSections sections={page.sections} image={(url, alt) => <PageImage url={url} alt={alt} token={page.publication_token} privatePreview />} />
    <SocialCardPreview title={page.title} description={page.description} url={page.canonical_url} image={page.cover ? <PageImage url={page.cover.url} alt={page.cover.alt} token={page.publication_token} privatePreview /> : undefined} />
  </div>;
}
