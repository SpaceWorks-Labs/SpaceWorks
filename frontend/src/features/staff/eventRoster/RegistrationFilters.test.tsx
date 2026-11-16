import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { RegistrationFiltersBar } from "./RegistrationFilters";

it("stacks the filter controls in one shrinkable column on a phone so selects never reach the screen edge", () => {
  render(<RegistrationFiltersBar value={{}} onChange={vi.fn()} tickets={[{ id: 1, name: "A very long ticket type name that would stretch a select" } as never]} />);
  const group = screen.getByRole("group", { name: "Filter registrations" });
  expect(group).toHaveClass("grid-cols-1", "sm:grid-cols-3");
  for (const select of screen.getAllByRole("combobox")) expect(select).toHaveClass("w-full", "min-w-0", "max-w-full");
});
