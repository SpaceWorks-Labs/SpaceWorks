import { t } from "@lingui/core/macro";
import { ArrowRight, ArrowUpRight, Building2, FileClock, KeyRound, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { CopyButton } from "../../docs/DocsCode";
import { DOCS_LINKS, GITHUB_URL, INSTALL_COMMAND } from "../hubLinks";

/** What Space Works is, as a statement and three promises the code keeps (the end of the hero sequence). */
export function IntroSection() {
  const promises = [
    { icon: FileClock, title: t`Every handover leaves a trail`, body: t`Scans, photos, remarks and an append-only audit log. Photo files can expire under a space’s retention policy; the record of who, what and when stays.` },
    { icon: Building2, title: t`Every space is its own`, body: t`One server can run many makerspaces. Each keeps its own inventory, team, public page, notifications and audit scope.` },
    { icon: KeyRound, title: t`Yours to run and to change`, body: t`Free software under the GNU AGPL. Install it on your own server, read every line, and keep your members’ data where you put it.` },
  ];
  return <section id="hub-intro" aria-labelledby="intro-title" className="sw-hub-section sw-hub-intro">
    <div className="sw-hub-wrap">
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:items-end md:gap-10">
        <h2 id="intro-title" className="sw-hub-h2">{t`One system for everything a shared workshop runs on.`}</h2>
        <p className="sw-hub-lede">{t`Members find tools, book time and sign up for events from their phone. Staff work one queue at the desk. Managers see the whole space, area by area.`}</p>
      </div>
      <ul className="mt-12 grid gap-8 md:grid-cols-3 md:gap-8 lg:mt-16">
        {promises.map(({ icon: Icon, title, body }) => <li key={title} className="grid content-start gap-3">
          <span className="sw-hub-area-icon" aria-hidden="true"><Icon size={20} /></span>
          <h3 className="text-xl font-extrabold text-ink">{title}</h3><p className="leading-7 text-muted">{body}</p>
        </li>)}
      </ul>
    </div>
  </section>;
}

/** Install → set up → run the desk: the sequence is the information, so the steps are numbered. */
export function HowItWorksSection() {
  const steps = [
    { title: t`Install once`, body: t`Run one command on a Linux server or a Mac. The installer asks for your web address, your space’s name and the areas you run, then starts everything. Run it again to update.` },
    { title: t`Set up your space`, body: t`Guided setup on the dashboard: name, logo, opening hours, areas and staff invitations. Every step can be skipped and picked up later.` },
    { title: t`Run the desk`, body: t`Members request and book from any phone. Staff accept, hand over with a scan and a photo, and take it back with a remark. Reports fill themselves in.` },
  ];
  return <section id="how" aria-labelledby="how-title" className="sw-hub-section sw-hub-band">
    <div className="sw-hub-wrap">
      <h2 id="how-title" className="sw-hub-h2 max-w-3xl">{t`From install to the front desk in an afternoon.`}</h2>
      <ol className="mt-10 grid gap-8 md:mt-14 md:grid-cols-3 md:gap-6">
        {steps.map((step, index) => <li key={step.title} className="sw-hub-step">
          <span className="sw-hub-step-number" aria-hidden="true">{index + 1}</span>
          <h3 className="text-2xl font-extrabold text-ink">{step.title}</h3>
          <p className="leading-7 text-muted">{step.body}</p>
        </li>)}
      </ol>
    </div>
  </section>;
}

/** The self-host call to action on the Deep Ink field, with the real one-line installer. */
export function SelfHostSection() {
  const facts = [
    t`Linux or macOS; Windows through WSL2`,
    t`Releases carry checksums and a keyless signature`,
    t`Keep everything on one server, or move the database, files, email or website elsewhere`,
  ];
  return <section id="self-host" aria-labelledby="selfhost-title" className="sw-hub-wrap pt-16 lg:pt-24">
    <div className="sw-island-dark sw-field-ink sw-hub-selfhost">
      <div className="grid content-start gap-5">
        <h2 id="selfhost-title" className="sw-hub-h2">{t`Your server. Your members. Your rules.`}</h2>
        <p className="sw-hub-lede">{t`Space Works installs with one command and updates the same way. Nobody else holds your members’ details, your photos or your books.`}</p>
        <ul className="grid gap-3">{facts.map(fact => <li key={fact} className="flex items-start gap-3">
          <ShieldCheck size={18} className="mt-1 shrink-0 text-accent-ink" aria-hidden="true" /><span>{fact}</span></li>)}</ul>
      </div>
      <div className="grid content-start gap-4">
        <figure className="sw-hub-terminal">
          <figcaption className="flex items-center justify-between gap-3 border-b border-line px-4 py-2 text-sm text-muted">
            <span>{t`Install or update`}</span><CopyButton text={INSTALL_COMMAND} label={t`Copy install command`} />
          </figcaption>
          <pre tabIndex={0} className="overflow-x-auto px-4 py-4 text-sm leading-6"><code className="code-text"><span aria-hidden="true" className="text-muted">$ </span>{INSTALL_COMMAND}</code></pre>
        </figure>
        <div className="flex flex-wrap gap-3">
          <Link to={DOCS_LINKS.install} className="desk-button-primary gap-2">{t`Read the install guide`}<ArrowRight size={16} aria-hidden="true" /></Link>
          <Link to={DOCS_LINKS.hosting} className="desk-button">{t`Compare hosting options`}</Link>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer noopener" className="desk-button gap-2">{t`Source on GitHub`}
            <ArrowUpRight size={16} aria-hidden="true" /><span className="sr-only">{t`(opens in a new tab)`}</span></a>
        </div>
      </div>
    </div>
  </section>;
}
