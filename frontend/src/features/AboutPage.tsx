import { t } from "@lingui/core/macro";
import { PublicLayout } from "../components/layouts";
import { ThemeToggle } from "../components/ThemeToggle";
import { ActionControl, ListRow } from "../components/ui";
import { LICENSE_URL } from "./inventory/PublicPageChrome";
import { WorkshopLogbook } from "../components/delight/WorkshopLogbook";
import { MakerModePanel, MakerModeToggle, useMakerMode, useShellMakerMode } from "../components/delight/EasterEggs";

function LocalMakerMode() {
  const mode = useMakerMode("/about");
  return <><MakerModeToggle mode={mode} /><MakerModePanel mode={mode} version="" /></>;
}
function AboutMakerMode() {
  const mode = useShellMakerMode();
  return mode ? <MakerModeToggle mode={mode} /> : <LocalMakerMode />;
}

/** About opens with a Citron field (brand p.2): ink statement type, teal caps eyebrow, teal primary. */
function AboutHero() {
  return <section aria-labelledby="about-title" className="sw-field-citron mb-8 grid gap-4 rounded-[20px] px-5 py-7 md:mb-10 md:gap-5 md:rounded-[28px] md:px-10 md:py-10">
    <p className="sw-field-eyebrow">{t`About`}</p>
    <h1 id="about-title" className="sw-field-heading">{t`Open-source makerspace management`}</h1>
    <p className="sw-hero-lede">{t`Tools to run a community workshop, with care for every handover.`}</p>
    <div><ActionControl action={{ label: t`Browse spaces`, href: "/" }} primary /></div>
  </section>;
}

export function AboutPage() {
  return <PublicLayout makerspace={{ name: "Space Works", slug: "", homeHref: "/" }} chrome="canvas"
    nav={[{ label: t`Browse spaces`, href: "/" }]} headerAction={{ label: t`Sign in`, href: "/member" }}
    liveStatus={<ThemeToggle variant="icon" />} width="narrow" state={{ status: "ready" }} hero={<AboutHero />}
    footer={{ credit: "Space Works · Made for shared workshops", links: [{ label: t`License`, href: LICENSE_URL, external: true }, { label: t`Staff sign-in`, href: "/admin" }] }}>
    <div className="space-y-5 text-base leading-7 text-muted">
      <p>{t`Space Works brings public equipment catalogues, traceable hardware loans, 3D-print requests, and makerspace operations together.`}</p>
      <p>{t`Each space controls its inventory, branding, team, and notifications. Members browse and request tools; staff review requests and record every issue and return with evidence.`}</p>
      <p>{t`Free and open source under the `}<a className="underline decoration-line underline-offset-4 hover:text-ink focus-visible:outline-2 focus-visible:outline-focus" href="https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/LICENSE" target="_blank" rel="noreferrer">{t`GNU Affero General Public License v3 ↗`}</a>. Use, study, share, and modify it under the licence terms.</p>
    </div>
    <WorkshopLogbook />
    <div className="mt-5"><AboutMakerMode /></div>
    <div className="mt-8 grid gap-4">
      <ListRow title={t`Browse spaces`} meta="Find a community workshop and explore its catalogue." href="/" right={<span aria-hidden="true">→</span>} />
      <ListRow title={t`Staff sign-in`} meta="Open the console for your makerspace." href="/admin" right={<span aria-hidden="true">→</span>} />
    </div>
  </PublicLayout>;
}
