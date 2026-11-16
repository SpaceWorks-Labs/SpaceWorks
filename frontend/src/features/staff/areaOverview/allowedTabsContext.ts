import { createContext } from "react";

/** The console tabs this person may open in the active space (permissions and switches
 * already applied by StaffTabContent), so a panel can link to its area's reports, audit
 * log and inbox without re-deriving access. Empty outside the console. */
export const AllowedTabsContext = createContext<readonly string[]>([]);
