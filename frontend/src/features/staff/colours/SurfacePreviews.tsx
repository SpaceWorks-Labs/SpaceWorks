import { t } from "@lingui/core/macro";
import type { CSSProperties, ReactNode } from "react";
import { brandContrastReport, brandPaletteStyle, deriveBrandPalette } from "../../../lib/brandColours";
import { previewBaseVars, type SurfaceId } from "../../../lib/colourSurfaces";
import { PrintedPreview } from "./PrintedPreview";

type Mode = "light" | "dark";
type Theme = Record<string, string>;

/**
 * One mock-up in one mode. It sets the very variables the app sets (base tokens plus the seven brand ones),
 * scoped to this box, so every class inside is the real utility. Decorative: hidden from assistive tech.
 */
function Frame({ mode, theme, scoped, id, children }: { mode: Mode; theme: Theme; scoped: boolean; id: SurfaceId; children: ReactNode }) {
  const valid = brandContrastReport(theme).valid;
  const brand = scoped ? brandPaletteStyle(deriveBrandPalette(valid ? theme : {}, mode)) : {};
  const style = { ...previewBaseVars(mode), ...brand } as CSSProperties;
  return <div data-testid={`preview-${id}-${mode}`} aria-hidden="true" inert style={style}
    className="min-w-0 overflow-hidden rounded-card border border-line bg-bg p-3 text-ink">
    <p className="mb-2 text-xs font-semibold text-muted">{mode === "light" ? t`Light` : t`Solid black`}</p>
    {children}
  </div>;
}

function StaffMock() {
  return <div className="grid grid-cols-[5.5rem_1fr] gap-2 text-xs">
    <div className="grid content-start gap-1 rounded-control bg-surface p-2">
      <span className="rounded-control bg-accent px-2 py-1 font-semibold text-on-accent">{t`Requests`}</span>
      <span className="px-2 py-1 text-muted">{t`Inventory`}</span>
      <span className="px-2 py-1 text-muted">{t`Members`}</span>
    </div>
    <div className="grid gap-2 rounded-control bg-panel p-2">
      <button type="button" tabIndex={-1} className="desk-button-primary justify-self-start">{t`Approve`}</button>
      <div className="flex items-center justify-between border-t border-line pt-2"><span>{t`3D printer kit`}</span>
        <span className="rounded-full bg-accent-soft px-2 py-0.5 font-semibold text-accent-ink">{t`Issued`}</span></div>
    </div>
  </div>;
}

function MemberMock() {
  return <div className="grid gap-2 rounded-card border border-line bg-panel p-3 text-sm">
    <p className="font-semibold">{t`Your loans`}</p>
    <p className="rounded-control bg-brand-soft p-2 text-xs">{t`Soldering station due Friday`}</p>
    <p><span className="font-semibold text-brand-ink underline">{t`View history`}</span></p>
    <button type="button" tabIndex={-1} className="desk-button-brand justify-self-start">{t`Request a tool`}</button>
  </div>;
}

function PublicMock() {
  return <div className="grid gap-2 rounded-card border border-line bg-panel p-4">
    <p className="text-lg font-extrabold">{t`Open this Saturday`}</p>
    <p className="text-xs text-muted">{t`Browse tools, book a bench, join an event.`}</p>
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" tabIndex={-1} className="desk-button-brand">{t`Browse inventory`}</button>
      <span className="text-sm font-semibold text-brand-ink underline">{t`See events`}</span>
    </div>
    <div className="rounded-control border border-brand-boundary p-2 text-xs text-brand-ink">{t`Outlined highlight`}</div>
  </div>;
}

function ScreenMock() {
  // Mirrors PublicStatsTvPage: ink numerals on panel tiles; only links carry the brand link colour.
  return <div className="grid grid-cols-2 gap-2 rounded-card bg-bg p-2 text-center">
    <div className="rounded-control border border-line bg-panel p-3"><p className="text-3xl font-extrabold text-ink">24</p><p className="text-xs text-muted">{t`Members in today`}</p></div>
    <div className="rounded-control border border-line bg-panel p-3"><p className="text-3xl font-extrabold text-ink">7</p><p className="text-xs text-muted">{t`Tools out`}</p></div>
    <p className="col-span-2 text-xs font-semibold text-brand-ink underline">{t`Next: Laser night`}</p>
  </div>;
}

export function SurfacePreview({ id, theme }: { id: SurfaceId; theme: Theme }) {
  const body = { staff: <StaffMock />, member: <MemberMock />, public: <PublicMock />, screens: <ScreenMock />, printed: null }[id];
  return <div className="grid gap-3 @lg:grid-cols-2">
    {(["light", "dark"] as const).map((mode) => <Frame key={mode} mode={mode} theme={theme} scoped={id !== "staff"} id={id}>
      {id === "printed" ? <PrintedPreview accent={theme.accent_color} mode={mode} /> : body}
    </Frame>)}
  </div>;
}
