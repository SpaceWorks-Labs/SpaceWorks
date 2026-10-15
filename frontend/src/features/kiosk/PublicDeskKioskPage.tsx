import { useParams } from "react-router-dom";
import { KioskLayout } from "../../components/layouts";
import { ThemeToggle } from "../../components/ThemeToggle";
import { PublicInventoryPage } from "../inventory/PublicInventoryPage";
import { useStationConnection } from "./useStationConnection";

// The catalogue owns its data and cart; the station only supplies touch-friendly chrome.
export function PublicDeskKioskPage() {
  const { slug = "" } = useParams();
  const online = useStationConnection();
  return <KioskLayout context={{ title: "Public desk", subtitle: "Explore the catalogue and request what you need." }}
    connection={{ online }} mode="work" state={{ status: "ready" }}
    headerActions={[{ label: "Open full catalogue", href: `/m/${slug}` }]}
    work={{ capture: <div className="text-lg [&_button]:min-h-12 [&_a]:min-h-12"><PublicInventoryPage embedded /></div>,
      panel: <div className="rounded-xl border border-line bg-panel p-6"><h2 className="title-panel">Find your next tool</h2><p className="mt-3 text-muted">Browse public equipment, then add the items you need to a request.</p><div className="mt-6"><ThemeToggle /></div></div> }} />;
}
