import { t } from "@lingui/core/macro";
import { useEffect, useMemo, useState } from "react";
import { SegmentedControl } from "../../../components/ui";
import type { StaffRole } from "../panels/rolesApi";
import { AreaSection } from "./AreaSection";
import { ModuleConfirm } from "./ModuleConfirm";
import { areasForRole, cardState, matches, roleUsage, type AreaModel, type CardModel, type FeatureModel, type StateFilter } from "./moduleModel";
import { planArea, planFeature, planModule, type Plan } from "./modulePlans";
import { ModulesToolbar, type ViewMode } from "./ModulesToolbar";
import type { useModuleSwitches } from "./useModuleSwitches";

type Switches = ReturnType<typeof useModuleSwitches>;

export function ModulesBody({ areas, roles, switches }: { areas: AreaModel[]; roles: StaffRole[]; switches: Switches }) {
  const [view, setView] = useState<ViewMode>("area");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<StateFilter>("all");
  const [roleSlug, setRoleSlug] = useState("");
  const target = useMemo(() => new URLSearchParams(window.location.search).get("module"), []);
  const [opened, setOpened] = useState<ReadonlySet<string>>(new Set(target ? [target] : []));
  useEffect(() => { if (target) document.getElementById(`module-${target}`)?.scrollIntoView?.({ block: "start" }); }, [target, areas.length]);
  const [pending, setPending] = useState<Plan | null>(null);
  const role = roles.find(item => item.slug === roleSlug) ?? roles[0];
  const names = useMemo(() => {
    const labels = new Map(areas.flatMap(area => area.cards).map(card => [card.key, card.label]));
    return (keys: string[]) => keys.map(key => labels.get(key) ?? key).join(", ");
  }, [areas]);

  const submit = async (plan: Plan) => { if (plan.confirm) setPending(plan); else await switches.apply(plan); };
  const actions = {
    busy: switches.busy,
    onToggle: (card: CardModel, on: boolean) => { if (cardState(card) !== "locked") void submit(planModule(areas, card, on)); },
    onFeature: (_card: CardModel, feature: FeatureModel, on: boolean) => void submit(planFeature(areas, feature, on)),
  };
  const shown = view === "role" && role ? areasForRole(areas, role) : areas;
  const visible = shown.map(area => ({ area, cards: area.cards.map(card => ({ card, ...matches(card, query, filter, switches.touched) })).filter(item => item.show) }))
    .filter(item => item.cards.length);
  const everyCard = shown.flatMap(area => area.cards);
  const counts: Record<StateFilter, number> = {
    all: everyCard.length, on: everyCard.filter(card => card.on).length, off: everyCard.filter(card => !card.on).length,
    locked: everyCard.filter(card => cardState(card) === "locked").length,
    changed: everyCard.filter(card => switches.touched.has(card.key) || card.features.some(feature => switches.touched.has(feature.key))).length,
  };
  const searching = query.trim() !== "";
  const usage = role ? roleUsage(areas, role) : null;
  const toggleOpen = (key: string, open: boolean) => setOpened(current => { const next = new Set(current); if (open) next.add(key); else next.delete(key); return next; });
  const shownCount = visible.reduce((sum, item) => sum + item.cards.length, 0);
  const viaFeature = new Set(visible.flatMap(item => item.cards.filter(entry => entry.viaFeature).map(entry => entry.card.key)));

  return <div className="grid min-w-0 gap-6">
    <ModulesToolbar view={view} onView={setView} query={query} onQuery={setQuery} filter={filter} onFilter={setFilter} counts={counts} />
    {view === "role" && roles.length ? <div className="grid min-w-0 gap-2">
      <SegmentedControl label={t`Role`} value={role?.slug ?? ""} onChange={setRoleSlug} options={roles.map(item => ({ value: item.slug, label: item.name }))} />
      {role && usage ? <p className="text-sm text-muted">{role.slug === "space_manager" ? t`${role.name} runs the whole space, so every area is shown.`
        : t`${role.name} uses ${usage.used} of ${usage.total} areas, worked out from what the role is allowed to do.`}</p> : null}
    </div> : null}
    {view === "role" && !roles.length ? <p role="status" className="text-sm text-muted">{t`Roles could not be loaded, so switches are shown by area.`}</p> : null}
    {switches.error ? <p role="alert" className="text-sm text-danger">{switches.error}</p> : null}
    <p role="status" aria-live="polite" className="sr-only">{t`${shownCount} areas shown`}</p>
    {visible.length === 0 ? <p className="rounded-control border border-line bg-panel p-4 text-sm text-muted">{searching ? t`Nothing matches this search and filter.` : t`Nothing here yet.`}</p> : null}
    {visible.map(({ area, cards }) => <AreaSection key={area.key} area={area} cards={cards.map(item => item.card)} actions={actions} names={names}
      opened={new Set([...opened, ...(searching ? viaFeature : [])])} onOpen={toggleOpen}
      onBulk={view === "area" ? (target, on) => void submit(planArea(areas, target, on)) : undefined} />)}
    <ModuleConfirm confirm={pending?.confirm ?? null} pending={switches.busy} onCancel={() => setPending(null)}
      onConfirm={() => { const plan = pending; setPending(null); if (plan) void switches.apply(plan); }} />
  </div>;
}
