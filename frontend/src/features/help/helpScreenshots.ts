export type HelpScreenshot = { src: string; width: number; height: number };

/** Only genuine captures reviewed against the exact guide step belong here.
 * Import each local asset so Vite also checks that the shipped file exists.
 * Unmapped editorial keys stay in Markdown and produce no placeholder UI.
 */
export const HELP_SCREENSHOTS: Readonly<Record<string, HelpScreenshot>> = {};
