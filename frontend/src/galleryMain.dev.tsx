// Dev-only entry for /gallery.html (`npm run dev`). Not an entry of the production build: vite builds
// index.html only, and gallery.html is not referenced from rollupOptions.input.
// Activates the catalogue before any module that renders text is evaluated.
import "./lib/i18n";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { initializeTheme } from "./lib/theme";
import { LayoutGallery } from "./components/layouts/LayoutGallery";
import { layoutGalleryExamples, type LayoutGalleryExampleName } from "./components/layouts/LayoutGalleryExamples";
import "./index.css";
initializeTheme();
const requested = new URLSearchParams(location.search).get("layout");
const initial: LayoutGalleryExampleName = layoutGalleryExamples.find(name => name === requested) ?? "Dashboard";
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <BrowserRouter><LayoutGallery initialExample={initial} /></BrowserRouter>,
);
