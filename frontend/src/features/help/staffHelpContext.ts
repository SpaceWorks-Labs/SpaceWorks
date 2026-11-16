import { createContext } from "react";

export type StaffHelpPlace = {
  makerspace?: { slug: string; enabled_features?: string[] };
  singleTenant?: boolean;
  platform?: boolean;
};

/** Set by the staff workspace: where a sub-screen's Help link points. Outside it a sub-screen shows no link. */
export const StaffHelpContext = createContext<StaffHelpPlace | null>(null);
