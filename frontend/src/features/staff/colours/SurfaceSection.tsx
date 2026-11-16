import { t } from "@lingui/core/macro";
import { useLabels, type Surface } from "../../../lib/colourSurfaces";
import type { Theme } from "../../../lib/colourFix";
import { SurfacePreview } from "./SurfacePreviews";

/** One audience group: who sees it, which space colours it takes, and its live previews. */
export function SurfaceSection({ surface, theme }: { surface: Surface; theme: Theme }) {
  const labels = useLabels();
  const headingId = `colour-surface-${surface.id}`;
  return <section aria-labelledby={headingId} data-surface={surface.id} className="@container grid min-w-0 content-start gap-3 rounded-card border border-line bg-panel p-4">
    <div>
      <h4 id={headingId} className="title-section">{surface.title}</h4>
      <p className="text-sm text-muted">{t`Seen by: ${surface.audience}`} · {surface.roles.join(", ")}</p>
    </div>
    <p className="text-sm"><span className="font-semibold">{t`Uses:`}</span> {labels[surface.uses]}. <span className="text-muted">{surface.examples}.</span></p>
    <p className="text-sm text-muted">{surface.note}</p>
    <SurfacePreview id={surface.id} theme={theme} />
  </section>;
}
