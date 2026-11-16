import { render as rtlRender, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// Screens now read query-backed switches (help-centre bootstrap, #184 charge flags), so every render needs a client.
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children?: Parameters<typeof rtlRender>[0] }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return rtlRender(ui, { wrapper, ...options });
}
import { MemoryRouter, useLocation } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { AppRoutes } from "./AppRoutes";

vi.mock("./features/public/MakerspacePage", () => ({ MakerspacePage: () => null }));
vi.mock("./features/staff/StaffApp", () => ({ StaffApp: () => null }));
vi.mock("./features/staff/PlatformApps", () => ({ SuperadminPage: () => null }));
vi.mock("./features/kiosk/PublicDeskKioskPage", () => ({ PublicDeskKioskPage: () => null }));
vi.mock("./features/kiosk/ScannerPage", () => ({ ScannerPage: () => null }));
vi.mock("./features/members/MemberArea", () => ({ MemberArea: () => {
  const location = useLocation();
  return <output>{location.pathname}{location.search}</output>;
} }));

it.each([
  ["single", "/member"], ["central", "/member"], ["central", "/m/lab/member"],
] as const)("retains %s legacy inbox proof redirects without depending on membership", async (mode, base) => {
  render(<MemoryRouter initialEntries={[`${base}/inbox?code=provider-code&state=signed&section=preferences`]}>
    <AppRoutes mode={mode} landing={null} />
  </MemoryRouter>);
  expect(await screen.findByText(`${base}/account-portal?code=provider-code&state=signed&section=preferences`)).toBeInTheDocument();
});
