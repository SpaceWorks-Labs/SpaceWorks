import { lazy } from "react";

/** The superadmin's platform pages after Overview and Spaces; they need no chosen space. */
export const PLATFORM_CONSOLE_PAGES: readonly string[] = ["platform-inbox", "platform-access", "platform-security", "platform-data", "platform-limits", "platform", "platform-analytics"];

// Lazy: the pages pull in every platform panel, which a space's staff never load.
export const PlatformConsoleContent = lazy(() => import("./PlatformConsoleContent").then(m => ({ default: m.PlatformConsoleContent })));
