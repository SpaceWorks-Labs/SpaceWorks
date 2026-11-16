import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { DeploymentNotices } from "./DeploymentNotices";

describe("DeploymentNotices accessibility", () => {
  it("groups the existing managed/free warnings with a valid accessible name", async () => {
    const { container } = render(<DeploymentNotices data={{ mode: "managed", profile: "free", scanner: "none", media_validation_available: false }} />);
    const group = screen.getByRole("group", { name: "Deployment notices" });
    expect(group).toHaveTextContent("Malware scanning is off.");
    expect(group).toHaveTextContent("Managed recovery");
    expect(group).toHaveTextContent("Free hosting is best effort.");
    expect(group).toHaveTextContent("Some media uploads are unavailable.");
    expect(group).toHaveTextContent("Scheduled database backups are unavailable in this profile.");
    await expectNoA11yViolations(container);
  });

  it("keeps host/full profiles free of managed/free warnings", () => {
    render(<DeploymentNotices data={{ mode: "host", profile: "full", scanner: "clamav", media_validation_available: true }} />);
    expect(screen.getByRole("group", { name: "Deployment notices" })).toBeEmptyDOMElement();
  });
});
