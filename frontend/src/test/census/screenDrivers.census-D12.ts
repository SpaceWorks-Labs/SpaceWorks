import { fireEvent, screen } from "@testing-library/react";
import type { RouteCase } from "./source.census-D12";

// This is a GET lookup, not a platform-account mutation. Disabled query
// prerequisites must be met through the real native form, including empty cases.
export async function prepareScreen(row: RouteCase) {
  if (row.leaves?.includes("PlatformAccessPage")) {
    const input = await screen.findByLabelText("User name", { exact: true });
    fireEvent.change(input, { target: { value: "d12-operator" } });
    fireEvent.submit(screen.getByRole("form", { name: "Find an account" }));
  }
}
