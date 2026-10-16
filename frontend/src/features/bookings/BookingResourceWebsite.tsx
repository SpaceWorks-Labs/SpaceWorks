import { RestrictedMarkdown } from "../../components/RestrictedMarkdown";
import { PublicWebsiteImage } from "../../components/PublicWebsiteImage";
import type { BookingWebsite } from "./bookingWebsiteTypes";

/** Published website sections, nested under the resource page's "Resource details" section heading. */
export function BookingResourceWebsite({ page, slug }: { page: BookingWebsite; slug: string }) {
  return <div className="grid gap-8">
    {page.sections.map((section) => <section className="grid min-w-0 gap-3" key={section.slug} aria-label={section.title}>
      <h3 className="title-section">{section.title}</h3>
      {section.image_url ? <PublicWebsiteImage makerspaceSlug={slug} url={section.image_url} alt={section.image_alt_text || section.title} /> : null}
      <RestrictedMarkdown text={section.body} />
      {/^https?:\/\//i.test(section.url) ? <a className="inline-flex min-h-11 w-fit items-center break-all text-accent-ink underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" href={section.url} rel="noopener noreferrer">{section.title}</a> : null}
    </section>)}
  </div>;
}
