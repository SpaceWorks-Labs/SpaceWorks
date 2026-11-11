import { render, screen } from "@testing-library/react";
import { Suspense } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Makerspace } from "../../types/inventory";
import { LandingGate } from "./LandingGate";

const state = vi.hoisted(() => ({
  config: { loading: false, enabled: true },
  spaces: { data: [] as { slug: string }[] | undefined, isLoading: false },
}));
vi.mock("./useLandingEnabled", () => ({ useLandingEnabled: () => state.config }));
vi.mock("../inventory/usePublicInventory", () => ({ usePublicMakerspaces: () => state.spaces }));
vi.mock("../public/FamilyHome", () => ({ RouteFallback: () => <p role="status">Opening Space Works…</p> }));
vi.mock("../discover/spaces/SpacesPage", () => ({ SpacesPage: () => <h1>Spaces directory</h1> }));

const space = (n: number) => ({ name: `Space ${n}`, public_code: `C${n}`, slug: `space-${n}`, location: "Town" }) satisfies Makerspace;

function Where() { return <p data-testid="where">{useLocation().pathname}</p>; }
function renderFront() {
  return render(<MemoryRouter initialEntries={["/"]}><Suspense fallback={<p>suspended</p>}><Routes>
    <Route path="/" element={<LandingGate landing={<h1>Product landing</h1>} />} />
    <Route path="/m/:slug" element={<Where />} />
  </Routes></Suspense></MemoryRouter>);
}

beforeEach(() => {
  state.config = { loading: false, enabled: true };
  state.spaces = { data: [], isLoading: false };
});

describe("LandingGate", () => {
  it("shows the landing while the switch is on", () => {
    state.spaces = { data: [space(1)], isLoading: false };
    renderFront();
    expect(screen.getByRole("heading", { name: "Product landing" })).toBeInTheDocument();
  });

  it("shows a loading state, never the landing, until the switch is known", () => {
    state.config = { loading: true, enabled: true };
    renderFront();
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Product landing" })).not.toBeInTheDocument();
  });

  it("opens the only public space's home when the switch is off", () => {
    state.config = { loading: false, enabled: false };
    state.spaces = { data: [space(1)], isLoading: false };
    renderFront();
    expect(screen.getByTestId("where")).toHaveTextContent("/m/space-1");
  });

  it("waits for the spaces before choosing when the switch is off", () => {
    state.config = { loading: false, enabled: false };
    state.spaces = { data: undefined, isLoading: true };
    renderFront();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows the spaces directory when the switch is off and there are several spaces", async () => {
    state.config = { loading: false, enabled: false };
    state.spaces = { data: [space(1), space(2)], isLoading: false };
    renderFront();
    expect(await screen.findByRole("heading", { name: "Spaces directory" })).toBeInTheDocument();
  });
});
