import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { persistSelectedMakerspace } from "./staffTabs";
import { useStaffChargesOn } from "./useStaffChargesOn";

const spaces = [
  { id: 1, enabled_modules: ["events"], enabled_features: ["charges.enabled", "charges.events"] },
  { id: 2, enabled_modules: ["events"], enabled_features: ["charges.enabled"] },
];

function Probe({ id }: { id?: number }) {
  return <output>{useStaffChargesOn("events", id) ? "on" : "off"}</output>;
}

function show(id?: number) {
  const client = new QueryClient();
  client.setQueryData(["staff", "makerspaces"], spaces);
  render(<QueryClientProvider client={client}><Probe id={id} /></QueryClientProvider>);
}

describe("useStaffChargesOn with no id (#184)", () => {
  beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); });

  it("follows the console's selected space, so a free space shows no prices", () => {
    persistSelectedMakerspace(2);
    show();
    expect(screen.getByRole("status")).toHaveTextContent("off");
  });

  it("falls back to any tracking space only when nothing is selected", () => {
    show();
    expect(screen.getByRole("status")).toHaveTextContent("on");
  });
});
