// L3 card routes: the public card check, the ID-programme join page, and "My cards"
// (with the programme-invite accept page), in both the single-tenant and central URL forms.
import { Route, Routes } from "react-router-dom";

import { InviteAcceptPage } from "../members/wallet/InviteAcceptPage";
import { WalletPage } from "../members/wallet/WalletPage";
import { JoinPage } from "../organizations/idProgrammes/JoinPage";
import { CardVerifyPage } from "./CardVerifyPage";

export function CardRoutes() {
  return <Routes>
    <Route path="/verify/c/:token" element={<CardVerifyPage />} />
    <Route path="/o/:organizationSlug/ids/:programmeSlug" element={<JoinPage />} />
    <Route path="/member/cards" element={<WalletPage />} />
    <Route path="/member/cards/accept" element={<InviteAcceptPage />} />
    <Route path="/m/:slug/member/cards" element={<WalletPage />} />
    <Route path="/m/:slug/member/cards/accept" element={<InviteAcceptPage />} />
  </Routes>;
}
