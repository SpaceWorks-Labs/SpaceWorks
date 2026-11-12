import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";

import { MakerspaceFeatureSettings } from "./MakerspaceFeatureSettings";
import type { Makerspace } from "./panels/shared";

const makerspace = { id: 7, name: "Venue", slug: "venue", enabled_modules: ["events"], enabled_features: ["events.invites"] } as Makerspace;
const mount = (settings = makerspace) => render(<MemoryRouter initialEntries={["/admin/venue/settings"]}>
  <MakerspaceFeatureSettings makerspace={makerspace} settings={settings} loading={false} /></MemoryRouter>);

it("is a summary with no feature switches: one way to switch lives in Areas & add-ons", () => {
  mount();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("switch")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open Areas & add-ons" })).toHaveAttribute("href", expect.stringContaining("modules"));
});

it("lists areas with features on and deep-links each to its card", () => {
  mount();
  const link = screen.getByRole("link", { name: "Events" });
  expect(link.getAttribute("href")).toMatch(/modules.*\?module=events/);
  expect(screen.getByText(/1 of \d+ on/)).toBeVisible();
  expect(screen.queryByText("events")).not.toBeInTheDocument();
});

it("omits areas that have no feature switched on", () => {
  mount({ ...makerspace, enabled_features: [] });
  expect(screen.queryByRole("link", { name: "Events" })).not.toBeInTheDocument();
});
