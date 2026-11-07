import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { SpaceWorksLogo } from "../SpaceWorksLogo";
import { ActionControl, IdentityChip, PageHeader } from "../ui";
import type { Action, IconName, Identity, Tone } from "../ui";
import { toneSurfaceClasses } from "../ui/tones";
import { LayoutFrame, QueryContent } from "./LayoutFrame";
import type { LayoutProps } from "./types";

export type CenteredCardLayoutProps = Omit<LayoutProps, "width"> & {
  media?: { icon: IconName; tone: Tone } | { avatars: [Identity, Identity] } | { banner: Tone };
  eyebrow?: string;
  title: string;
  body: ReactNode;
  content?: ReactNode;
  primary: Action;
  escape?: Action;
  footer?: ReactNode;
  width?: 440 | 480 | "wide";
};
export function CenteredCardLayout({ media, eyebrow, title, body, content, primary, escape, footer,
  width = 440, standalone = true, ...query }: CenteredCardLayoutProps) {
  return <LayoutFrame standalone={standalone}>
    <a href="/" aria-label={t`Space Works — Open makerspace listing`} className="mb-8 inline-flex rounded-control focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
      <span className="inline-flex sm:hidden"><SpaceWorksLogo variant="stacked" size={180} /></span>
      <span className="hidden sm:inline-flex"><SpaceWorksLogo variant="horizontal" size={288} /></span>
    </a>
    <div className="grid min-h-[60dvh] items-center">
      <div className={`sw-centered-card ${width === "wide" ? "sw-centered-wide" : width === 480 ? "sw-centered-480" : ""}`}>
        {media ? <div className="mb-6">
          {"icon" in media ? <IdentityChip identity={{ kind: "icon", ...media }} label={title} />
            : "avatars" in media ? <div className="flex -space-x-3">{media.avatars.map((identity, index) => <IdentityChip key={index} identity={identity} />)}</div>
            : <div aria-hidden="true" className={`h-28 rounded-xl border ${toneSurfaceClasses[media.banner]}`} />}
        </div> : null}
        <PageHeader eyebrow={eyebrow} title={title} />
        <QueryContent {...query}>
          <div className="grid gap-6"><div className="text-base text-muted">{body}</div>{content}
            <ActionControl action={primary} primary className="w-full" />
            {escape ? <ActionControl action={escape} className="w-full border-transparent underline" /> : null}
            {footer ? <div className="border-t border-line pt-4 text-sm text-muted">{footer}</div> : null}
          </div>
        </QueryContent>
      </div>
    </div>
  </LayoutFrame>;
}
