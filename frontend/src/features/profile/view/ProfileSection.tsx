import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import type { Audience, SectionKey, Shown } from "../accountProfileTypes";

/**
 * One résumé block. For the owner a switched-off section still renders (so they can see what they have) and says
 * it is hidden; everyone else never receives a hidden section, so there is nothing to mark.
 */
export function ProfileSection({ id, title, section, shown, audience, children }: {
  id: string; title: string; section: SectionKey; shown: Shown; audience: Audience; children: ReactNode;
}) {
  const hidden = audience === "owner" && !shown[section];
  return <section aria-labelledby={`profile-${id}`} className="grid gap-4 border-t border-line pt-6">
    <div className="flex flex-wrap items-center gap-3">
      <h2 id={`profile-${id}`} className="title-panel">{title}</h2>
      {hidden ? <span className="chip">{t`Hidden from others`}</span> : null}
    </div>
    {children}
  </section>;
}
