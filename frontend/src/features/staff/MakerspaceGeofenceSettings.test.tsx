import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { Makerspace } from "./StaffPanels";
import { MakerspaceGeofenceSettings } from "./MakerspaceGeofenceSettings";

it("explains the hard self check-in rule, GPS limits and the staff/kiosk alternative", () => {
  const space = { id: 7, geofence_enabled: false } as Makerspace;
  render(<QueryClientProvider client={new QueryClient()}>
    <MakerspaceGeofenceSettings makerspace={space} loading={false} />
  </QueryClientProvider>);
  expect(screen.getByText(/Self check-in requires a location inside the configured radius/)).toHaveTextContent(
    "Without a configured geofence, self check-in is unavailable. GPS can be spoofed. Staff or kiosk check-in is the alternative.",
  );
});
