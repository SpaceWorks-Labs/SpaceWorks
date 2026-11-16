import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { DisplayCanvas } from "./DisplayCanvas";
import { toInput, type Draft } from "./DisplayConfigFields";
import { resolveTheme, THEME_CLASS } from "./SpaceDisplayPage";
import { sampleState } from "./previewState";

const W = 1920;
const H = 1080;

/** Fit a 1920x1080 stage into whatever width the settings column has. */
function useStageScale() {
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0.25);
  useEffect(() => {
    const node = box.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => setScale(node.clientWidth / W));
    observer.observe(node);
    setScale(node.clientWidth / W);
    return () => observer.disconnect();
  }, []);
  return { box, scale };
}

/**
 * The screen as the draft would show it, drawn with sample people, events and numbers (never real
 * ones), so a manager sees layout, theme, order and privacy before saving anything.
 */
export function DisplayPreview({ draft, spaceName }: { draft: Draft; spaceName: string }) {
  const { box, scale } = useStageScale();
  const state = sampleState(toInput(draft), spaceName);
  return <figure className="grid gap-2" aria-label={t`Live preview with sample data`}>
    <div ref={box} className="relative w-full overflow-hidden rounded-xl border border-line" style={{ aspectRatio: `${W} / ${H}` }}>
      <div aria-hidden="true" inert className={`${THEME_CLASS[resolveTheme(draft.theme, undefined)]} absolute left-0 top-0 origin-top-left p-16`}
        style={{ width: W, height: H, transform: `scale(${scale})` }}>
        <p className={`mb-10 text-4xl font-semibold ${draft.theme === "brand" ? "text-accent" : ""}`}>{spaceName}</p>
        <DisplayCanvas state={state} now={Date.now()} />
      </div>
    </div>
    <figcaption className="text-xs text-muted">{t`Preview with sample data. Real names appear only as the privacy choice allows.`}</figcaption>
  </figure>;
}
