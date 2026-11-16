import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./lib/tenant", () => ({ useTenant: () => ({ mode: "single", loading: true, error: new Error("Tenant archived") }) }));
vi.mock("./AppRoutes", () => ({ AppRoutes: () => <p>Account recovery route</p> }));
vi.mock("./features/auth/ReauthenticationDialog", () => ({ ReauthenticationDialog: () => null }));

it.each(["/account/restore", "/member/archived"])("keeps %s reachable while tenant bootstrap is unavailable", path => {
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
  expect(screen.getByText("Account recovery route")).toBeInTheDocument();
  expect(screen.queryByText("Loading site…")).toBeNull();
});
