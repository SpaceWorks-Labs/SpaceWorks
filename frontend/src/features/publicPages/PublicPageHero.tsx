import { t } from "@lingui/core/macro";
import { PageImage } from "./PageImage";
import type { PublicPageProjection } from "./pageTypes";
import { ActionControl, type Action } from "../../components/ui";

export function PublicPageHero({ page, slug, actions = [] }: { page: PublicPageProjection; slug?: string; actions?: Action[] }) {
  return <header className="mb-8 grid min-w-0 gap-5">
    {page.cover ? <PageImage url={page.cover.url} alt={page.cover.alt} slug={slug} token={page.publication_token} /> : null}
    <div className="rounded-xl border border-line bg-panel p-5 md:p-8">
      <p className="eyebrow mb-3">{page.kind === "makerspace" ? t`Makerspace` : t`Organization`}</p>
      <h1 className="title-page break-words">{page.title}</h1>
      {page.description ? <p className="mt-3 max-w-3xl whitespace-pre-wrap text-muted">{page.description}</p> : null}
      {actions.length ? <nav aria-label={t`Quick actions`} className="mt-5 flex flex-wrap gap-2">{actions.map((action, index) => <ActionControl key={action.label} action={action} primary={index === 0} />)}</nav> : null}
    </div>
  </header>;
}
