import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api/errors";
import { SettingsQueryState } from "./SettingsQueryState";

it.each([
  [403, "permission_denied"], [404, "module_disabled"], [404, "feature_disabled"],
  [404, "not_found"], [503, "service_unavailable"], [429, "throttled"],
] as const)("settings read pairs message and retry for %s %s", (status, code) => {
  const detail = "This settings read was refused.";
  const error = new StructuredApiError(status, { code, detail });
  const refetch = vi.fn();
  render(<SettingsQueryState query={{ error, refetch }} resource="settings"><p>Editor</p></SettingsQueryState>);
  expect({ status: error.status, code: error.code }).toEqual({ status, code });
  if (status === 503 || status === 429) {
    expect(screen.getByText("Couldn't load settings. Try again.")).toBeVisible();
    screen.getByRole("button", { name: "Retry" }).click();
    expect(refetch).toHaveBeenCalledTimes(1);
  } else {
    expect(screen.getByText(detail)).toBeVisible();
    expect(screen.queryByRole("button", { name: /retry|try again/i })).toBeNull();
    expect(screen.queryByText(/couldn't load|try again/i)).toBeNull();
    expect(refetch).not.toHaveBeenCalled();
  }
});
