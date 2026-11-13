import { t } from "@lingui/core/macro";
import { ArrowLeft, ChevronRight } from "lucide-react";
import { consoleSessionHref, currentSessionContext } from "../../../lib/api/sessionContext";
import { TAB_LABELS } from "../staffTabLabels";
import { staffTabPath } from "../staffTabs";

/**
 * Open item A30 (U11): when the platform superadmin works inside one space (a health "Fix", an
 * "Open" from Spaces), every page keeps the same header -- Platform › Space › Area -- and a way
 * back, instead of dropping them into a space console that looks like a different product.
 */
export function PlatformSpaceBreadcrumb({ spaceName, tab }: { spaceName: string; tab: string }) {
  if (currentSessionContext() !== "platform") return null;
  const back = consoleSessionHref(staffTabPath("platform-spaces", false), "platform");
  const area = TAB_LABELS[tab] ?? null;
  return <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-sm">
    <nav aria-label={t`Breadcrumb`} className="min-w-0">
      <ol className="flex flex-wrap items-center gap-1 text-muted">
        <li><a className="underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-focus" href={back}>{t`Platform`}</a></li>
        <li aria-hidden="true"><ChevronRight size={14} /></li>
        <li className="break-words font-semibold text-ink" aria-current={area ? undefined : "page"}>{spaceName}</li>
        {area ? <><li aria-hidden="true"><ChevronRight size={14} /></li><li className="text-ink" aria-current="page">{area}</li></> : null}
      </ol>
    </nav>
    <a className="desk-button-ghost" href={back}><ArrowLeft aria-hidden="true" size={14} />{t`Back to platform`}</a>
  </div>;
}
