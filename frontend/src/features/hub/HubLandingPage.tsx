import { t } from "@lingui/core/macro";
import { Fragment, useRef, type ComponentType } from "react";
import { PageMetadata } from "../../components/PageMetadata";
import { HubFooter } from "./HubFooter";
import { HubHeader } from "./HubHeader";
import { AreasSection } from "./landing/AreasSection";
import { FaqSection } from "./landing/FaqSection";
import { HandoverScrolly } from "./landing/HandoverScrolly";
import { HeroSection } from "./landing/HeroSection";
import { OpenSourceSection } from "./landing/OpenSourceSection";
import { AppsSection, DocsSection } from "./landing/ReachSections";
import { SkipAhead } from "./landing/SkipAhead";
import { HowItWorksSection, SelfHostSection } from "./landing/StorySections";
import { useRevealOnScroll } from "./landing/useInView";
import "./hub.css";

type Part = { id: string; next?: { id: string; label: string }; Section: ComponentType; reveal: boolean };

/** After the hero: each section in order, the skip link that jumps past it, and whether it rises in. */
function parts(): Part[] {
  return [
    { id: "handover", next: { id: "areas", label: t`Skip to the areas` }, Section: HandoverScrolly, reveal: false },
    { id: "areas", next: { id: "how", label: t`Skip to how it works` }, Section: AreasSection, reveal: true },
    { id: "how", next: { id: "self-host", label: t`Skip to self-hosting` }, Section: HowItWorksSection, reveal: true },
    { id: "self-host", next: { id: "open-source", label: t`Skip to the licence` }, Section: SelfHostSection, reveal: true },
    { id: "open-source", next: { id: "apps", label: t`Skip to the apps` }, Section: OpenSourceSection, reveal: true },
    { id: "apps", next: { id: "docs", label: t`Skip to the documentation` }, Section: AppsSection, reveal: true },
    { id: "docs", next: { id: "faq", label: t`Skip to the questions` }, Section: DocsSection, reveal: true },
    { id: "faq", Section: FaqSection, reveal: true },
  ];
}

/**
 * The central hub's front page ("/"): a pinned opening that carries the tagline into the staff console
 * and on to the overview, a sample loan told step by step beside a pinned record, then the areas, how
 * it works, self-hosting, the licence, the apps, the docs and the common
 * questions, each rising in once as it arrives. Fully static: the spaces directory lives at /spaces
 * (linked from the header), not on this page. The handover section is never wrapped for reveal: a transformed
 * ancestor would break its pinned stage.
 */
export function HubLandingPage() {
  const main = useRef<HTMLElement>(null);
  useRevealOnScroll(main);
  return <div className="sw-hub">
    <PageMetadata title={t`Space Works · Open-source makerspace management`} path="/" image="/brand/og-1200x630.png"
      imageAlt={t`The Space Works logo`} siteName="Space Works"
      description={t`Free, self-hosted software for makerspaces, fab labs and community workshops: inventory and tool loans with evidence, machines, events, bookings, a shop and memberships.`} />
    <a href="#hub-main" className="skip-link">{t`Skip to content`}</a>
    <HubHeader />
    <main ref={main} id="hub-main" tabIndex={-1} className="outline-none">
      <HeroSection />
      {parts().map(({ id, next, Section, reveal }) => <Fragment key={id}>
        {next ? <SkipAhead target={next.id} label={next.label} /> : null}
        {reveal ? <div data-reveal=""><Section /></div> : <Section />}
      </Fragment>)}
    </main>
    <HubFooter />
  </div>;
}
