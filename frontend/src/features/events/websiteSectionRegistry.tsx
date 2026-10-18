import type { ReactNode } from "react";
import { PublicPageSections } from "../publicPages/PublicPageSections";
import type { PublicPageProjection, PublicPageSection } from "../publicPages/pageTypes";

export const eventSectionProviderVersion = 1;
export const eventEditorialTypes = ["about", "gallery", "team", "testimonials", "links"] as const;
type EditorialType = typeof eventEditorialTypes[number];
export type EventSectionProvider<K extends EditorialType> = {
  schema_version: 1; key: K;
  render: (section: Extract<PublicPageSection, { type: K }>, image: (url: string, alt: string) => ReactNode) => ReactNode;
};
function provider<K extends EditorialType>(key: K): EventSectionProvider<K> {
  return { schema_version: 1, key, render: (section, image) => <PublicPageSections sections={[section]} image={image} /> };
}
/** Only server-projected, registered sections render. Adding a provider also requires its backend schema/gates. */
export const eventSectionProviders = {
  about: provider("about"), gallery: provider("gallery"), team: provider("team"), testimonials: provider("testimonials"), links: provider("links"),
} satisfies { [K in EditorialType]: EventSectionProvider<K> };
// Reserved names are documentation, never writable provider registrations.
export const futureEventProviders = ["prizes", "judges", "mentors", "project_gallery", "results"] as const;
export function EventEditorialSections({ projection, image }: { projection: Pick<PublicPageProjection, "schema_version" | "sections">; image: (url: string, alt: string) => ReactNode }) {
  if (projection.schema_version !== eventSectionProviderVersion) return null;
  return <div className="grid gap-8">{projection.sections.map(section => {
    let content: ReactNode;
    switch (section.type) {
      case "about": content = eventSectionProviders.about.render(section, image); break;
      case "gallery": content = eventSectionProviders.gallery.render(section, image); break;
      case "team": content = eventSectionProviders.team.render(section, image); break;
      case "testimonials": content = eventSectionProviders.testimonials.render(section, image); break;
      case "links": content = eventSectionProviders.links.render(section, image); break;
      default: return null;
    }
    return <div key={section.id}>{content}</div>;
  })}</div>;
}
