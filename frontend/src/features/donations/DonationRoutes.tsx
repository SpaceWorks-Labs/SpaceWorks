import { Route, Routes } from "react-router-dom";

import { NotFoundPage } from "../NotFoundPage";
import { DonatePage } from "./DonatePage";
import { GuestGiftPage } from "./GuestGiftPage";
import { GuestPledgePage } from "./GuestPledgePage";

/** `/donate` on a tenant domain and `/m/:slug/donate` centrally (the paths the receipt emails link to). */
export function DonationRoutes() {
  return <Routes>
    <Route path="/donate" element={<DonatePage />} />
    <Route path="/donate/gift/:token" element={<GuestGiftPage />} />
    <Route path="/donate/pledge/:token" element={<GuestPledgePage />} />
    <Route path="/m/:slug/donate" element={<DonatePage />} />
    <Route path="/m/:slug/donate/gift/:token" element={<GuestGiftPage />} />
    <Route path="/m/:slug/donate/pledge/:token" element={<GuestPledgePage />} />
    <Route path="*" element={<NotFoundPage />} />
  </Routes>;
}
