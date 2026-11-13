import { t } from "@lingui/core/macro";
import { ArrowLeft, ArrowRight, Download } from "lucide-react";
import { Link, Navigate, useParams } from "react-router-dom";
import { PageMetadata } from "../../../components/PageMetadata";
import { PatchMoment } from "../../../components/delight/PatchMoment";
import { moduleLabel } from "../../../lib/moduleLabels";
import { TransitionLink } from "../../../lib/motion";
import { NotFoundPage } from "../../NotFoundPage";
import { HubFooter } from "../HubFooter";
import { HubHeader } from "../HubHeader";
import { DOCS_LINKS } from "../hubLinks";
import { featureCatalogue } from "./catalogue";
import { defaultLabel, moduleDocs } from "./featureSummary";
import { moduleDefault } from "./featureAreas";
import { FeatureList, Lines, Panel } from "./ModuleSections";
import { featuresByModule } from "./moduleFeatures";
import { moduleFromSlug, moduleGroups, retiredModuleRedirect } from "./moduleGroups";
import "../hub.css";
import "./features.css";

/**
 * /features/<module> (decision 328 b): ONE template for all modules. What it shows is data: the catalogue
 * (what it does, reports, analytics, limits, integrations), the feature definitions (its switches) and the
 * module's group. A retired module's page redirects to the module it is part of; an unknown one is the 404.
 */
export function FeatureModulePage() {
  const slug = useParams().module;
  const key = moduleFromSlug(slug);
  const redirect = retiredModuleRedirect(slug);
  if (redirect) return <Navigate to={redirect} replace />;
  if (!key) return <NotFoundPage />;
  const entry = featureCatalogue()[key];
  const features = featuresByModule()[key];
  const group = moduleGroups().find(row => row.modules.includes(key));
  const label = moduleLabel(key);
  const Icon = entry.icon;
  const docs = moduleDocs(key);
  return <div className="sw-hub">
    <PageMetadata title={t`${label} · Features · Space Works`} path={`/features/${key.replace(/_/g, "-")}`} siteName="Space Works"
      description={`${entry.value} ${entry.what}`.slice(0, 200)} />
    <a href="#hub-main" className="skip-link">{t`Skip to content`}</a>
    <HubHeader />
    <main id="hub-main" tabIndex={-1} className="outline-none">
      <section aria-labelledby="module-title" className="sw-hub-wrap sw-features-hero sw-features-module-hero">
        <div className="grid content-start gap-5">
          <TransitionLink to="/features" className="sw-hub-inline-link inline-flex w-fit items-center gap-1">
            <ArrowLeft size={16} aria-hidden="true" />{t`All modules`}</TransitionLink>
          <span className="sw-features-card-icon" aria-hidden="true"><Icon size={24} /></span>
          <h1 id="module-title" className="sw-features-title">{label}</h1>
          <p className="sw-hub-lede">{entry.what}</p>
          <p className="sw-features-card-meta">
            <span>{group?.title}</span>
            <span className="sw-features-default" data-default={moduleDefault(key)}>{defaultLabel(key)}</span>
          </p>
          <div className="flex flex-wrap gap-3">
            <Link to={DOCS_LINKS.install} className="desk-button-primary min-h-12 gap-2 px-5"><Download size={18} aria-hidden="true" />{t`Install Space Works`}</Link>
            <Link to="/spaces" className="desk-button min-h-12 gap-2 px-5">{t`Try it in a live space`}</Link>
          </div>
        </div>
        <div className="sw-features-shots" data-shots={entry.screenshots?.length ?? 0}>
          {entry.screenshots?.length
            ? entry.screenshots.map(shot => <figure key={shot.src}><img src={shot.src} alt={shot.alt} loading="lazy" /><figcaption>{shot.caption}</figcaption></figure>)
            : <PatchMoment className="sw-features-patch" />}
        </div>
      </section>
      <div className="sw-hub-wrap sw-features-panels">
        {entry.newIn?.length ? <Panel kind="new" title={t`New in 0.12.0`}><Lines items={entry.newIn} empty="" /></Panel> : null}
        <Panel kind="who" title={t`Who uses it`}><Lines items={entry.roles} empty={t`Everyone who signs in.`} /></Panel>
        <Panel kind="integrations" title={t`Integrations`}><Lines items={entry.integrations} empty={t`It works on its own, with nothing to connect.`} /></Panel>
        <Panel kind="features" title={t`Features (${features.length})`}><FeatureList features={features} /></Panel>
        <Panel kind="reports" wide={entry.reports.length > 8} title={t`Reports`}
          note={entry.reports.length ? t`Every report shows on screen, exports to CSV, XLSX or PDF, can be scheduled by email, and reads in Metabase, Grafana or the API. Space managers see their own space; the platform owner sees roll-ups.` : undefined}>
          <Lines items={entry.reports.map(report => report.title)} empty={t`No reports of its own; its activity shows in the module health report.`} /></Panel>
        <Panel kind="analytics" title={t`Analytics`}><Lines items={entry.analytics} empty={t`No separate analytics.`} /></Panel>
        <Panel kind="limits" title={t`Limits`} note={t`Limits are off by default and set by the platform operator: a default per module, overridable for one space. Space Managers see their usage read-only, with a warning at 80% and new items blocked at 100%.`}>
          <Lines items={entry.limits} empty={entry.noLimits ?? t`No limits for this module.`} /></Panel>
      </div>
      <section className="sw-hub-wrap sw-features-more">
        <Link to={docs} className="sw-hub-inline-link inline-flex w-fit items-center gap-1">{t`Read the ${label} docs`}<ArrowRight size={16} aria-hidden="true" /></Link>
      </section>
    </main>
    <HubFooter />
  </div>;
}
