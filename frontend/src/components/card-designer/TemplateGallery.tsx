// "Start from a template": the six templates drawn live (front and back) for the current
// preview person, in light or dark. Choosing one replaces the draft after a confirmation.
import { t } from "@lingui/core/macro";
import { useMemo, useState, useSyncExternalStore } from "react";
import { LayoutTemplate } from "lucide-react";

import { ConfirmDialog } from "../ui/ConfirmDialog";
import { ErrorBlock } from "../ui/ErrorBlock";
import { Modal } from "../ui/Modal";
import { SegmentedControl } from "../ui/SegmentedControl";
import type { CardDesign, CardTemplate } from "./cardTypes";
import { fitInside } from "./canvasMath";
import { CardThumbnail } from "./CardThumbnail";
import { useResetDesign, useTemplates } from "./designerApi";
import { useCardFonts } from "./useCardFonts";
import { LogoLoader } from "../LogoLoader";

const WIDE = "(min-width: 640px)";
function useWide() {
  return useSyncExternalStore((notify) => {
    const media = window.matchMedia?.(WIDE);
    media?.addEventListener?.("change", notify);
    return () => media?.removeEventListener?.("change", notify);
  }, () => window.matchMedia?.(WIDE).matches ?? true, () => true);
}

export function TemplateGallery({ design, values, onAdopt, onError }: {
  design: CardDesign; values: Record<string, string>; onAdopt: (design: CardDesign) => void; onError: (error: unknown) => void;
}) {
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [chosen, setChosen] = useState<CardTemplate | null>(null);
  const templates = useTemplates(design.id, open);
  const reset = useResetDesign(design.id);
  const wide = useWide();
  const shown = useMemo(() => (templates.data ?? []).filter((item) => item.theme === theme), [templates.data, theme]);
  useCardFonts(design.id, useMemo(() => shown.map((item) => item.document), [shown]));
  const box = wide ? 190 : 136;

  function apply() {
    if (!chosen) return;
    reset.mutateAsync({ template: chosen.key, theme: chosen.theme })
      .then((saved) => { onAdopt(saved); setChosen(null); setOpen(false); })
      .catch((error) => { setChosen(null); setOpen(false); onError(error); });
  }

  return <>
    <button type="button" className="desk-button min-h-11" onClick={() => setOpen(true)}>
      <LayoutTemplate size={16} aria-hidden="true" /> {t` Templates`}</button>
    <Modal open={open} onClose={() => setOpen(false)} title={t`Start from a template`} size="xl">
      <div className="grid gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted">{t`Shown with ${values.name}. Every template stays fully editable.`}</p>
          <SegmentedControl label={t`Template colours`} value={theme} onChange={(value) => setTheme(value as "light" | "dark")}
            options={[{ value: "light", label: t`Light` }, { value: "dark", label: t`Dark` }]} />
        </div>
        {templates.isLoading ? <LogoLoader size={48} className="min-h-44 py-3" /> : null}
        {templates.isError ? <ErrorBlock error={templates.error} resource={t`templates`} onRetry={() => void templates.refetch()} /> : null}
        {templates.data && !shown.length ? <p className="text-sm text-muted">{t`No ${theme} templates are available.`}</p> : null}
        <ul className="grid gap-3 sm:grid-cols-2" aria-label={theme === "light" ? t`Light templates` : t`Dark templates`}>
          {shown.map((item) => {
            const { front, back, back_enabled: twoSided, mono } = item.document;
            const width = fitInside(box, box * 0.75, front.page_width_mm, front.page_height_mm);
            return <li key={`${item.key}-${item.theme}`} className="grid gap-3 rounded-card border border-line bg-surface p-3">
              <div className="flex flex-wrap items-start justify-center gap-2">
                <CardThumbnail side={front} designId={design.id} values={values} mono={mono} width={width}
                  label={t`${item.label}, ${item.theme}, front`} />
                {twoSided ? <CardThumbnail side={back} designId={design.id} values={values} mono={mono} width={width}
                  label={t`${item.label}, ${item.theme}, back`} /> : null}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-semibold text-ink">{item.label}
                  <span className="block text-xs font-normal text-muted">{twoSided ? t`Two-sided` : t`Front only`}</span></span>
                <button type="button" className="desk-button-primary min-h-11" disabled={reset.isPending}
                  onClick={() => setChosen(item)}>{t`Use ${item.label}`}</button>
              </div>
            </li>;
          })}
        </ul>
      </div>
    </Modal>
    <ConfirmDialog open={chosen !== null} title={chosen?.label ? t`Start again from ${chosen.label}?` : t`Start again from this template?`}
      message={t`Your draft is replaced. Cards keep the published version until you publish again.`}
      confirmLabel={t`Replace the draft`} pending={reset.isPending} onCancel={() => setChosen(null)} onConfirm={apply} />
  </>;
}
