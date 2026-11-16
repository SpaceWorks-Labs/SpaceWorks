import type { ReactNode } from "react";
import { ActionControl } from "./ActionControl";
import { IdentityChip } from "./IdentityChip";
import { OverflowMenu } from "./OverflowMenu";
import type { Action, Identity, PageHeaderProps } from "./types";
export type PageHeaderDetailSlots = { back?: Action; identity?: Identity; status?: ReactNode;
  /** Set the title in the Unbounded accent (one accent per layout). */
  accentTitle?: boolean };
export function PageHeader({ eyebrow, title, subtitle, meta, primary, secondary, overflow = [],
  back, identity, status, headingLevel = 1, stickyPrimaryOnMobile = false, accentTitle = false }: PageHeaderProps & PageHeaderDetailSlots) {
  const Heading = headingLevel === 2 ? "h2" : "h1";
  const mobileActions = secondary ? "menu" in secondary ? secondary.menu : [secondary] : [];
  return <header className="mb-6 min-w-0">
    {back ? <div className="mb-8"><ActionControl action={{ ...back, icon: "ArrowLeft" }} className="border-transparent bg-transparent px-0 text-sm text-accent-ink hover:bg-transparent hover:underline" /></div> : null}
    {eyebrow ? <p className="mb-2 text-sm text-muted">{eyebrow}</p> : null}
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-0 flex-1 basis-full items-center gap-3 sm:basis-0">
        {identity ? <IdentityChip identity={identity} label={title} /> : null}
        <div className="min-w-0">
          <Heading className={`title-page break-words${accentTitle ? " font-accent" : ""}`}>{title}</Heading>
          {subtitle ? <p className="mt-2 text-base text-muted">{subtitle}</p> : null}
          {meta || status ? <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">{status}{meta}</div> : null}
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        {secondary ? <div className="hidden md:block">{"menu" in secondary
          ? <OverflowMenu label={secondary.label} actions={secondary.menu} /> : <ActionControl action={secondary} />}</div> : null}
        {primary ? <div className={stickyPrimaryOnMobile ? "sw-sticky-primary" : ""}><ActionControl action={primary} primary className={stickyPrimaryOnMobile ? "w-full md:w-auto" : ""} /></div> : null}
        <OverflowMenu actions={overflow} mobileActions={mobileActions} className={overflow.length ? "" : "md:hidden"} />
      </div>
    </div>
  </header>;
}
