import { pageInput, pageLabel } from "./documentDefaults";
import type { AccentChoice, PageAsset, PageDocument } from "./pageTypes";

export const paletteSeeds: Record<Exclude<AccentChoice, "inherit">, string> = {
  maker_teal: "#006E63", workshop_orange: "#FF7447", citron: "#DFFF8F", sky_blue: "#B5CDFF", warm_yellow: "#FFD447",
};
const labels: Record<AccentChoice, string> = { inherit: "Inherit", maker_teal: "Maker Teal", workshop_orange: "Workshop Orange", citron: "Citron", sky_blue: "Sky Blue", warm_yellow: "Warm Yellow" };
export function PagePresentationForm({ document, assets, choices, disabled, onChange }: {
  document: PageDocument; assets: Pick<PageAsset, "id" | "alt_text">[]; choices: AccentChoice[]; disabled: boolean; onChange: (document: PageDocument) => void;
}) {
  return <fieldset disabled={disabled} className="grid gap-4 rounded-xl border border-line p-4">
    <legend className="px-1 font-semibold">Cover and colours</legend>
    <label className={pageLabel}>Cover<select className={pageInput} value={document.cover_mode} onChange={e => onChange({ ...document,
      cover_mode: e.target.value as PageDocument["cover_mode"], cover_asset_id: e.target.value === "asset" ? document.cover_asset_id : null })}>
      <option value="inherit">Inherit existing cover or logo</option><option value="asset">Use an uploaded image</option><option value="none">No cover</option>
    </select></label>
    {document.cover_mode === "asset" ? <label className={pageLabel}>Cover image<select className={pageInput} required value={document.cover_asset_id ?? ""}
      onChange={e => onChange({ ...document, cover_asset_id: e.target.value ? Number(e.target.value) : null })}>
      <option value="">Choose an image</option>{assets.map(asset => <option key={asset.id} value={asset.id}>{asset.alt_text}</option>)}
    </select></label> : null}
    <fieldset className="grid gap-2"><legend className="mb-2 text-sm font-semibold">Public accent palette</legend>
      <div className="flex flex-wrap gap-2">{choices.map(choice => <label key={choice} className="flex min-h-11 cursor-pointer items-center gap-2 rounded-control border border-line px-3 text-sm has-checked:border-brand-boundary has-checked:bg-brand-soft">
        <input type="radio" name="page-accent" value={choice} checked={(document.accent_choice ?? "inherit") === choice} onChange={() => onChange({ ...document, accent_choice: choice })} />
        {choice !== "inherit" ? <span aria-hidden="true" className="h-5 w-5 rounded-full border border-line" style={{ backgroundColor: paletteSeeds[choice] }} /> : null}{labels[choice]}
      </label>)}</div>
    </fieldset>
    <p className="text-sm text-muted">Colours apply to the public preview and page. Inherit keeps existing brand colours, including custom colours.</p>
  </fieldset>;
}
