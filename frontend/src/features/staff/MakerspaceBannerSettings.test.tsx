import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { MakerspaceBrandingSettings } from "./MakerspaceBrandingSettings";

vi.mock("./MakerspaceThemeSettings", () => ({ MakerspaceThemeSettings: () => null }));
vi.mock("./ImageUploader", () => ({ ImageUploader: (props: {
  endpoint: string; currentUrl?: string | null; label: string; shape?: string; onChanged: () => void;
}) => <button data-endpoint={props.endpoint} data-current={props.currentUrl} data-shape={props.shape} onClick={props.onChanged}>{props.label}</button> }));

it("labels the existing makerspace cover uploader Banner and refreshes the public home and listing caches", async () => {
  const space = { id: 7, name: "Lab", slug: "lab", public_code: "LAB1", telegram_group_chat_id: "",
    frontend_domain: null, hidden_from_central_directory: false, cover_image_url: "https://cdn.test/public-images/lab/banner.webp" };
  const cache = new QueryClient();
  const keys = [["makerspace-settings", 7], ["public-makerspaces"], ["tenant-bootstrap", "lab"],
    ["runtime-tenant"], ["runtime-tenant-origin"], ["member", "lab", "bootstrap"], ["staff", "makerspaces"]];
  for (const key of keys) cache.setQueryData(key, space);
  render(<QueryClientProvider client={cache}><MakerspaceBrandingSettings makerspace={space} settings={space} loading={false} /></QueryClientProvider>);
  expect(screen.getByText("Banner", { exact: true })).toBeVisible();
  const banner = screen.getByRole("button", { name: "Banner (wide image)" });
  expect(banner).toHaveAttribute("data-endpoint", "/admin/makerspace/7/cover");
  expect(banner).toHaveAttribute("data-current", space.cover_image_url);
  expect(banner).toHaveAttribute("data-shape", "wide");
  fireEvent.click(banner);
  await waitFor(() => { for (const key of keys) expect(cache.getQueryState(key)?.isInvalidated).toBe(true); });
});
