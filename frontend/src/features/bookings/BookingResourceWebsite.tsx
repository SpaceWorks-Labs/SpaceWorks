import { RestrictedMarkdown } from "../../components/RestrictedMarkdown";
import { PublicWebsiteImage } from "../../components/PublicWebsiteImage";
import type { BookingWebsite } from "./bookingWebsiteTypes";

export function BookingResourceWebsite({ page, slug }: { page: BookingWebsite; slug: string }) {
  return <div className="grid gap-5" aria-label="Resource website">
    {page.sections.map((section) => <section className="desk-panel p-5" key={section.slug}>
      <h2 className="title-section">{section.title}</h2>
      {section.image_url ? <PublicWebsiteImage makerspaceSlug={slug} url={section.image_url} alt={section.image_alt_text || section.title} /> : null}
      <RestrictedMarkdown text={section.body} />
      {/^https?:\/\//i.test(section.url) ? <a className="underline" href={section.url} rel="noopener noreferrer">{section.title}</a> : null}
    </section>)}
  </div>;
}
