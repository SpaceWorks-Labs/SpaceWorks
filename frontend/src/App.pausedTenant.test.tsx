import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import App from "./App";
import { StructuredApiError } from "./lib/api/errors";

// #185(1): a paused space served on its own domain or tenant token shows the paused page, not "Site unavailable".
vi.mock("./lib/tenant", () => ({ useTenant: () => ({ mode: "single", loading: false,
  error: new StructuredApiError(404, { detail: "This space is paused.", code: "space_paused" }) }) }));
vi.mock("./AppRoutes", () => ({ AppRoutes: () => <p>Routes</p> }));
vi.mock("./features/auth/ReauthenticationDialog", () => ({ ReauthenticationDialog: () => null }));

it("shows the paused page for a paused own-domain space", () => {
  render(<MemoryRouter initialEntries={["/"]}><App /></MemoryRouter>);
  expect(screen.getByText("This space is paused")).toBeInTheDocument();
  expect(screen.queryByText("Site unavailable")).toBeNull();
});
