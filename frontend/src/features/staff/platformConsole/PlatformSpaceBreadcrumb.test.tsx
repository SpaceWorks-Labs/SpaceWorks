import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { setRouteSessionContext } from "../../../lib/api/sessionContext";
import { PlatformSpaceBreadcrumb } from "./PlatformSpaceBreadcrumb";

afterEach(() => setRouteSessionContext("person"));

describe("Platform › Space › Area header (open item A30)", () => {
  it("names the platform, the space and the area with a way back", () => {
    setRouteSessionContext("platform");
    render(<PlatformSpaceBreadcrumb spaceName="North Lab" tab="settings" />);
    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(nav).toHaveTextContent("Platform");
    expect(nav).toHaveTextContent("North Lab");
    expect(screen.getByText("Settings")).toHaveAttribute("aria-current", "page");
    const back = screen.getByRole("link", { name: "Back to platform" });
    expect(back.getAttribute("href")).toContain("/admin/platform-spaces");
    expect(back.getAttribute("href")).toContain("context=platform");
  });

  it("stays out of a normal staff session", () => {
    setRouteSessionContext("person");
    const { container } = render(<PlatformSpaceBreadcrumb spaceName="North Lab" tab="settings" />);
    expect(container).toBeEmptyDOMElement();
  });
});
