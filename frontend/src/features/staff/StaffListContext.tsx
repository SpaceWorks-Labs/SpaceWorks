import { createContext } from "react";

export const StaffListContext = createContext<{ ownerName: string; canShare: boolean; actorId?: number; actions?: readonly string[]; isSuperadmin?: boolean; makerspace?: { id: number; enabled_modules?: string[]; enabled_features?: string[] } }>({ ownerName: "", canShare: false });
