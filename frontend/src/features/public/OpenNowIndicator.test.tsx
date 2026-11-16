import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { TenantBootstrap } from "../../lib/api";
import { OpenNowIndicator } from "./OpenNowIndicator";

function bootstrap(open_status?: TenantBootstrap["makerspace"]["open_status"]) {
  return { makerspace: { timezone: "UTC", open_status } } as unknown as TenantBootstrap;
}

const now = Date.parse("2026-11-12T10:00:00Z");

describe("OpenNowIndicator", () => {
  it("renders nothing when the space records no hours", () => {
    const { container } = render(<OpenNowIndicator bootstrap={bootstrap()} now={now} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("says open now with the closing time", () => {
    render(<OpenNowIndicator now={now} bootstrap={bootstrap({ open_now: true, closes_at: "2026-11-12T17:00:00Z", next_opens_at: null })} />);
    expect(screen.getByRole("status")).toHaveTextContent(/Open now · closes .*5:00/);
  });

  it("says closed now with the next opening", () => {
    render(<OpenNowIndicator now={now} bootstrap={bootstrap({ open_now: false, closes_at: null, next_opens_at: "2026-11-13T09:00:00Z" })} />);
    expect(screen.getByRole("status")).toHaveTextContent(/Closed now · next opens .*9:00/);
  });

  it("drops a status the page has outlived instead of guessing", () => {
    const { container } = render(<OpenNowIndicator now={Date.parse("2026-11-12T18:00:00Z")}
      bootstrap={bootstrap({ open_now: true, closes_at: "2026-11-12T17:00:00Z", next_opens_at: null })} />);
    expect(container).toBeEmptyDOMElement();
  });
});
