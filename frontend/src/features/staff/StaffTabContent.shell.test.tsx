import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import { StaffTabContent } from "./StaffTabContent";
import type { ComponentProps } from "react";
it("W39 a non-global tab with no active makerspace renders the real No makerspace panel", () => {
  const props = { activeTab: "inventory", activeMakerspace: undefined } as ComponentProps<typeof StaffTabContent>;
  render(<MemoryRouter><StaffTabContent {...props} /></MemoryRouter>);
  expect(screen.getByRole("heading", { name: "No makerspace" })).toBeInTheDocument();
});
