import { fireEvent, render, screen } from "@testing-library/react";
import { Suspense } from "react";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AboutLandingGate, LandingGate } from "./LandingGate";

const state = vi.hoisted(() => ({
  config: { loading: false, enabled: true },
  spaces: { data: [] as { slug: string }[] | undefined, isLoading: false, isError: false },
}));
vi.mock("./useLandingEnabled", () => ({ useLandingEnabled: () => state.config }));
vi.mock("../inventory/usePublicInventory", () => ({ usePublicMakerspaces: () => state.spaces }));
vi.mock("../public/FamilyHome", () => ({ RouteFallback: () => <p role="status">Opening Space Works</p> }));
vi.mock("../discover/spaces/SpacesPage", () => ({ SpacesPage: () => <h1>Spaces directory</h1> }));

const space = (n: number) => ({ slug: `space-${n}` });
function Where() { const navigate = useNavigate(); return <><p data-testid="where">{useLocation().pathname}</p><button onClick={() => navigate(-1)}>Back</button></>; }
function renderFront(path = "/") {
  return render(<MemoryRouter initialEntries={["/previous", path]}><Suspense fallback={<p>suspended</p>}><Routes>
    <Route path="/" element={<LandingGate landing={<h1>Product landing</h1>} />} />
    <Route path="/about" element={<AboutLandingGate landing={<h1>Product landing</h1>} />} />
    <Route path="/m/:slug" element={<Where />} /><Route path="/previous" element={<Where />} />
  </Routes></Suspense></MemoryRouter>);
}
beforeEach(() => {
  state.config = { loading: false, enabled: true };
  state.spaces = { data: [], isLoading: false, isError: false };
});
describe("LandingGate decision 424", () => {
  it("shows landing on an empty deployment", () => {
    renderFront(); expect(screen.getByRole("heading", { name: "Product landing" })).toBeInTheDocument();
  });
  it("shows landing when the backend fails, including a failed refetch", () => {
    state.spaces = { data: [space(1)], isLoading: false, isError: true };
    renderFront(); expect(screen.getByRole("heading", { name: "Product landing" })).toBeInTheDocument();
  });
  it.each([true, false])("opens the only public space with landing=%s", enabled => {
    state.config.enabled = enabled; state.spaces.data = [space(1)]; renderFront();
    expect(screen.getByTestId("where")).toHaveTextContent("/m/space-1");
  });
  it.each([true, false])("shows the directory for three spaces with landing=%s", async enabled => {
    state.config.enabled = enabled; state.spaces.data = [space(1), space(2), space(3)]; renderFront();
    expect(await screen.findByRole("heading", { name: "Spaces directory" })).toBeInTheDocument();
  });
  it.each([true, false])("waits for spaces without flashing landing with landing=%s", enabled => {
    state.config.enabled = enabled; state.spaces = { data: undefined, isLoading: true, isError: false }; renderFront();
    expect(screen.getByRole("status")).toBeInTheDocument(); expect(screen.queryByRole("heading")).toBeNull();
  });
  it("waits until the switch is known", () => {
    state.config.loading = true; renderFront(); expect(screen.getByRole("status")).toBeInTheDocument();
  });
  it.each([false, true])("keeps the directory on empty/error when the switch is off (error=%s)", async isError => {
    state.config.enabled = false; state.spaces.isError = isError; renderFront();
    expect(await screen.findByRole("heading", { name: "Spaces directory" })).toBeInTheDocument();
  });
  it("keeps the landing reachable at /about with existing spaces", () => {
    state.spaces.data = [space(1), space(2)]; renderFront("/about");
    expect(screen.getByRole("heading", { name: "Product landing" })).toBeInTheDocument();
  });
  it("redirects /about through the homepage rules when disabled", () => {
    state.config.enabled = false; state.spaces.data = [space(1)]; renderFront("/about");
    expect(screen.getByTestId("where")).toHaveTextContent("/m/space-1");
  });
  it("waits for config on /about", () => {
    state.config.loading = true; renderFront("/about"); expect(screen.getByRole("status")).toBeInTheDocument();
  });
});

it("replaces the homepage history entry when opening the only space", () => {
  state.spaces.data = [space(1)]; renderFront();
  fireEvent.click(screen.getByRole("button", { name: "Back" }));
  expect(screen.getByTestId("where")).toHaveTextContent("/previous");
});
