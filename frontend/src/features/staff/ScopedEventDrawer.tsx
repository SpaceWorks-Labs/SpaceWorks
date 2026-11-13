import { EventDrawer } from "./EventDrawer";
import { SpaceScope, useSpaceSwitches } from "./SpaceScope";

type Props = { slug: string; eventId: number; makerspaceId: number; onClose: () => void; onOpenSeries?: (seriesId: number) => void };

/**
 * Open items A19/A20: an event drawer opened from a cross-space list (assigned events, organized
 * events). It takes the event space's switches and re-scopes the staff context to that space, so the
 * feature-gated sections and the related-activity, linked-finance and cross-link panels appear.
 */
export function ScopedEventDrawer({ slug, ...props }: Props) {
  return <SpaceScope makerspaceId={props.makerspaceId} slug={slug}><Drawer slug={slug} {...props} /></SpaceScope>;
}

function Drawer({ slug, ...props }: Props) {
  const space = useSpaceSwitches(props.makerspaceId, slug);
  return <EventDrawer {...props} enabledFeatures={space.features} enabledModules={space.modules} />;
}
