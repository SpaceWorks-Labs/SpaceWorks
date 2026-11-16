import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PlatformDeploymentSection } from "./PlatformDeploymentSection";
import { getPlatformDashboard } from "./platformMonitoringApi";
vi.mock("./platformMonitoringApi", () => ({ getPlatformDashboard: vi.fn() }));
vi.mock("../deployment/DeploymentPanel", () => ({ DeploymentPanel: ({ data }: { data: { mode: string } }) => <p>{data.mode} deployment</p> }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><PlatformDeploymentSection /></QueryClientProvider>);
}
it("mounts the authorized deployment projection", async () => {
  vi.mocked(getPlatformDashboard).mockResolvedValue({ deployment: { mode: "managed" } } as Awaited<ReturnType<typeof getPlatformDashboard>>);
  mount();
  expect(await screen.findByText("managed deployment")).toBeTruthy();
  expect(getPlatformDashboard).toHaveBeenCalledTimes(1);
});
it("keeps failed infrastructure reads in the existing error boundary", async () => {
  vi.mocked(getPlatformDashboard).mockRejectedValue(new Error("unavailable"));
  mount();
  expect(await screen.findByText("Couldn't load deployment information. Try again.")).toBeTruthy();
});
