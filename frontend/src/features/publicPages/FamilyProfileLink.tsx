import { RouteLink } from "../../components/ui/RouteLink";
import { usePublicPage } from "./pageApi";

/** The family stays the home. The server alone decides whether its separate profile is public. */
export function FamilyProfileLink({ slug }: { slug: string }) {
  const query = usePublicPage("makerspace", slug);
  if (query.error || !query.data) return null;
  return <aside aria-label="Makerspace public profile" className="border-t border-line bg-panel px-5 py-3 text-center">
    <RouteLink className="desk-button" href={query.data.canonical_url}>About {query.data.title}</RouteLink>
  </aside>;
}
