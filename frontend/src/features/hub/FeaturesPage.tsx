import { t } from "@lingui/core/macro";
import { ArrowRight, Download, Search } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PageMetadata } from "../../components/PageMetadata";
import { PatchMoment } from "../../components/delight/PatchMoment";
import { moduleLabel } from "../../lib/moduleLabels";
import { TransitionLink } from "../../lib/motion";
import { featureCatalogue, newInRelease } from "./featuresPage/catalogue";
import { moduleSummary } from "./featuresPage/featureSummary";
import { ModuleCard } from "./featuresPage/ModuleCard";
import { featuresByModule } from "./featuresPage/moduleFeatures";
import { moduleGroups, moduleSlug } from "./featuresPage/moduleGroups";
import { HubFooter } from "./HubFooter";
import { HubHeader } from "./HubHeader";
import { DOCS_LINKS } from "./hubLinks";
import "./hub.css";
import "./featuresPage/features.css";

/**
 * /features (decisions 306 and 328 b): every module as a card, grouped like the module switch screens, each
 * opening /features/<module>. Everything shown is data: the groups mirror the backend registry, the counts come
 * from the same catalogue and feature definitions the module pages list. Public; it works whether or not the
 * landing switch is on (decision 306 c).
 */
export function FeaturesPage() {
  const [query, setQuery] = useState("");
  const searchId = useId();
  const groups = useMemo(moduleGroups, []);
  const total = useMemo(() => {
    const keys = groups.flatMap(group => group.modules);
    return { modules: keys.length, features: keys.reduce((sum, key) => sum + moduleSummary(key).features, 0),
      reports: keys.reduce((sum, key) => sum + moduleSummary(key).reports, 0) };
  }, [groups]);
  const needle = query.trim().toLowerCase();
  const visible = useMemo(() => {
    const catalogue = featureCatalogue();
    const byModule = featuresByModule();
    const matches = (key: (typeof groups)[number]["modules"][number]) => !needle || [moduleLabel(key), catalogue[key].value,
      ...catalogue[key].reports.map(report => report.title), ...catalogue[key].integrations, ...byModule[key].map(feature => feature.label)]
      .some(text => text.toLowerCase().includes(needle));
    return groups.map(group => ({ ...group, modules: group.modules.filter(matches) })).filter(group => group.modules.length);
  }, [groups, needle]);
  return <div className="sw-hub">
    <PageMetadata title={t`Features · Space Works`} path="/features" siteName="Space Works"
      description={t`Every Space Works module and what it does: features, reports, limits and integrations for inventory, machines, events, bookings, membership, payments, the shop and more.`} />
    <a href="#hub-main" className="skip-link">{t`Skip to content`}</a>
    <HubHeader />
    <main id="hub-main" tabIndex={-1} className="outline-none">
      <section aria-labelledby="features-title" className="sw-hub-wrap sw-features-hero">
        <h1 id="features-title" className="sw-features-title">{t`Everything Space Works does, module by module.`}</h1>
        <p className="sw-hub-lede">{t`Each makerspace turns on the modules it runs. Open one to see its features, reports, limits and integrations. Turn one off and it leaves every screen; its history stays.`}</p>
        <p className="text-sm font-medium text-muted">{t`${total.modules} modules · ${total.features} features · ${total.reports} reports`}</p>
        <div className="sw-features-search">
          <label htmlFor={searchId} className="sr-only">{t`Search modules and features`}</label>
          <Search size={18} aria-hidden="true" />
          <input id={searchId} type="search" value={query} onChange={event => setQuery(event.target.value)}
            placeholder={t`Search modules, features and reports`} autoComplete="off" />
        </div>
        {needle ? null : <nav aria-label={t`Groups on this page`}>
          <ul className="sw-features-jump">{groups.map(group => <li key={group.key}><a href={`#group-${group.key}`}>{group.title}</a></li>)}</ul>
        </nav>}
      </section>
      {needle ? null : <section aria-labelledby="new-title" className="sw-hub-wrap sw-features-new">
        <h2 id="new-title" className="title-section">{t`New in 0.12.0`}</h2>
        <ul>{newInRelease().map(item => <li key={item.title} data-new={item.module}>
          <TransitionLink to={`/features/${moduleSlug(item.module)}`} className="font-semibold text-ink">{item.title}</TransitionLink>
          <span className="text-sm text-muted">{item.line}</span></li>)}</ul>
      </section>}
      <div className="sw-hub-wrap">
        {visible.map(group => <section key={group.key} id={`group-${group.key}`} aria-labelledby={`group-${group.key}-title`} className="sw-features-group">
          <div className="grid content-start gap-2">
            <h2 id={`group-${group.key}-title`} className="sw-features-area-title">{group.title}</h2>
            <p className="sw-hub-lede">{group.summary}</p>
          </div>
          <ul className="sw-features-grid" data-count={Math.min(group.modules.length, 3)}>{group.modules.map(key => <ModuleCard key={key} module={key} solo={group.modules.length === 1} />)}</ul>
        </section>)}
        {visible.length ? null : <p role="status" className="sw-features-empty">{t`No module matches "${query}". Try a shorter word.`}</p>}
      </div>
      {/* Patch is this closing section's one bold moment, so its buttons stay teal (no orange beside it). */}
      <section aria-labelledby="features-cta-title" className="sw-hub-wrap">
        <div className="sw-features-cta">
          <div className="grid content-start gap-4">
            <h2 id="features-cta-title" className="sw-hub-h2">{t`Start with what you run today.`}</h2>
            <p className="sw-hub-lede">{t`Install once, pick your modules, and add the rest when you need them.`}</p>
            <div className="flex flex-wrap gap-3">
              <Link to={DOCS_LINKS.install} className="desk-button-primary min-h-12 gap-2 px-5"><Download size={18} aria-hidden="true" />{t`Install Space Works`}</Link>
              <Link to="/spaces" className="desk-button min-h-12 gap-2 px-5">{t`Find a live space`}<ArrowRight size={18} aria-hidden="true" /></Link>
            </div>
          </div>
          <PatchMoment className="sw-features-patch" />
        </div>
      </section>
    </main>
    <HubFooter />
  </div>;
}
