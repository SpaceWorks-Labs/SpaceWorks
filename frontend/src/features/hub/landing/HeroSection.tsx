import { t } from "@lingui/core/macro";
import { ArrowRight, Download } from "lucide-react";
import { useRef } from "react";
import { Link } from "react-router-dom";
import { ExternalLink } from "../ExternalLink";
import { DOCS_LINKS, GITHUB_URL } from "../hubLinks";
import { DeskPreview } from "./DeskPreview";
import { SkipAhead } from "./SkipAhead";
import { IntroSection } from "./StorySections";
import { useScrollSequence } from "./useScrollSequence";
import "./landing-scroll.css";
import "./symbol-pattern.css";

/**
 * The opening: the tagline and two ways in, then the staff console rises into view, the view moves
 * through its request list, and the overview settles in its place (useScrollSequence). DOM order is
 * reading order: copy, console, overview. Static, in that order, under reduced motion, on phones and on
 * screens too short to hold a scene. The page's one Workshop Orange moment is the install button.
 */
export function HeroSection() {
  const sequence = useRef<HTMLDivElement>(null);
  const { jumpToEnd } = useScrollSequence(sequence);
  return <div ref={sequence} className="sw-hub-seq">
    <SkipAhead target="hub-intro" label={t`Skip to the overview`} onJump={jumpToEnd} />
    <div className="sw-hub-seq-scene" data-seq="scene">
      <div className="sw-hub-pattern" aria-hidden="true" />
      <div className="sw-hub-seq-backdrop" data-seq="backdrop" aria-hidden="true" />
      <section aria-labelledby="hub-title" className="sw-hub-seq-copy" data-seq="copy">
        <div className="sw-hub-wrap grid justify-items-center gap-6 text-center md:gap-7">
          <h1 id="hub-title" className="sw-hero-title sw-hub-hero-title">{t`Run the space, not spreadsheets.`}</h1>
          <p className="sw-hub-hero-lede">{t`Space Works is free, open-source software for makerspaces, fab labs and community workshops. Lend tools with proof of every handover, book machines and rooms, run events and keep the money straight, on a server you control.`}</p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link to={DOCS_LINKS.install} className="sw-hub-cta-primary"><Download size={18} aria-hidden="true" />{t`Install Space Works`}</Link>
            <Link to="/spaces" className="sw-hub-cta-outline">{t`Find a space`}<ArrowRight size={18} aria-hidden="true" /></Link>
            <Link to="/features" className="sw-hub-hero-more">{t`See every feature`}<ArrowRight size={16} aria-hidden="true" /></Link>
          </div>
          <p className="flex flex-wrap justify-center gap-x-2 text-sm font-medium text-muted">
            <ExternalLink href={GITHUB_URL} iconSize={14} className="sw-hub-hero-source"
              label={t`Open source under AGPL-3.0: the Space Works repository on GitHub (opens in a new tab)`}>{t`Open source under AGPL-3.0`}</ExternalLink>
            {[t`Self-hosted`, t`No licence fees`].map(fact => <span key={fact} className="inline-flex gap-x-2 whitespace-nowrap">
              <span aria-hidden="true">·</span><span>{fact}</span></span>)}
          </p>
        </div>
      </section>
      <div className="sw-hub-seq-stage" data-seq="stage">
        <div className="sw-hub-wrap"><div className="sw-hub-seq-frame" data-seq="frame"><DeskPreview /></div></div>
      </div>
      <div className="sw-hub-seq-reveal" data-seq="reveal">
        <SkipAhead target="handover" label={t`Skip to how a handover works`} />
        <IntroSection />
      </div>
    </div>
  </div>;
}
