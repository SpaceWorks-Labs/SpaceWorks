import { Card } from "../../components/ui/Card";
import { EmptyState as EmptyCard } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/Spinner";
import type { PublicCategory } from "../../types/inventory";

export type View =
  | { kind: "all" }
  | { kind: "sort"; sort: "popular" | "most_used" }
  | { kind: "category"; slug: string };

export function formatSlug(slug: string): string {
  return slug
    .split("-")
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

export function LoadingState() {
  return (
    <div className="grid min-h-64 place-items-center">
      <Spinner />
    </div>
  );
}

export function EmptyState({ query }: { query: string }) {
  return <EmptyCard message={query
    ? "No matching items. Try a different search or clear the search field."
    : "No public items yet. Check back after this makerspace shares its tools."} />;
}

export function ErrorState({ error }: { error: Error }) {
  return (
    <Card className="mx-auto max-w-lg border-brand text-center">
      <h2 className="title-panel">{error.message}</h2>
      <p className="mt-2 text-sm leading-6 text-muted">
        This makerspace may not exist or its public inventory is disabled.
      </p>
    </Card>
  );
}

export function CatalogSidebar({ categories, view, onSelect }: { categories: PublicCategory[]; view: View; onSelect: (view: View) => void }) {
  const choices: { label: string; value: View; active: boolean; count?: number }[] = [
    { label: "All items", value: { kind: "all" }, active: view.kind === "all" },
    { label: "Popular", value: { kind: "sort", sort: "popular" }, active: view.kind === "sort" && view.sort === "popular" },
    { label: "Most used", value: { kind: "sort", sort: "most_used" }, active: view.kind === "sort" && view.sort === "most_used" },
    ...categories.map(category => ({ label: category.name, value: { kind: "category" as const, slug: category.slug }, active: view.kind === "category" && view.slug === category.slug, count: category.product_count })),
  ];
  return <nav aria-label="Catalog browse" className="flex gap-2 overflow-x-auto pb-2">{choices.map(choice =>
    <button key={choice.label} className={choice.active ? "desk-button-brand shrink-0" : "desk-button shrink-0"} aria-current={choice.active ? "page" : undefined} onClick={() => onSelect(choice.value)} type="button">
      {choice.label}{choice.count != null ? <span className="ml-2 tabular-nums">({choice.count})</span> : null}
    </button>)}</nav>;
}
