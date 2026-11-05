import { Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useTenant } from "../../../lib/tenant";
import { useTenantBootstrap } from "../../inventory/usePublicInventory";
import { ProgrammeAccess } from "../programme/ProgrammeAccess";
import { Reimbursements, ReimbursementRequest, ReimbursementClaim, ReimbursementAppeal } from "../reimbursements";
import { StageForms, StageForm } from "../stagedForms";
import { MemberPayoutHistory, MemberPayoutDetail } from "../../finance/eventPayouts";
import { MyPrizes } from "../prizes";
import { eventAddonPaths, eventPayoutPaths, memberEventAddonHref, prizePaths } from "./routeNames";

/** The makerspace comes from the tenant context, never from an unchecked URL label. */
function useMakerspace() {
  const tenant = useTenant();
  const { slug } = useParams();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const bootstrap = useTenantBootstrap(makerspaceSlug, tenant.mode === "central" && Boolean(makerspaceSlug));
  const makerspaceId = tenant.mode === "single" ? tenant.makerspaceId : bootstrap.data?.makerspace.id ?? null;
  return { slug: makerspaceSlug, makerspaceId, loading: tenant.loading || bootstrap.isLoading };
}

type AddonKind = "reimbursement" | "stages" | "response";

function EventAddonPage({ kind }: { kind: AddonKind }) {
  const params = useParams();
  const navigate = useNavigate();
  const space = useMakerspace();
  const eventId = Number(params.eventId);
  if (space.loading) return <p role="status">Loading…</p>;
  if (!space.makerspaceId || !Number.isSafeInteger(eventId)) return <p role="alert">This event page is unavailable here.</p>;
  const makerspaceId = space.makerspaceId;
  const go = (suffix: string) => navigate(memberEventAddonHref(space.slug, eventId, suffix));
  const payouts = `${space.slug ? `/m/${encodeURIComponent(space.slug)}` : ""}/member/event-payouts`;
  return <ProgrammeAccess slug={space.slug}>{user => {
    const scope = { actorId: user.id, makerspaceId, eventId };
    if (kind === "response") return <StageForm scope={scope} responseId={Number(params.responseId)} />;
    if (kind === "stages") return <StageForms scope={scope} onOpen={responseId => go(`stage-responses/${responseId}`)} />;
    if (params.view === "request") return <ReimbursementRequest scope={scope} />;
    if (params.view === "claim") return <ReimbursementClaim scope={scope} />;
    if (params.view === "appeal") return <ReimbursementAppeal scope={scope} />;
    return <Reimbursements scope={scope} onRequest={() => go("reimbursement/request")} onClaim={() => go("reimbursement/claim")}
      onAppeal={() => go("reimbursement/appeal")} onPayout={id => navigate(`${payouts}/${id}`)} />;
  }}</ProgrammeAccess>;
}

/** Owner payout history works on any live host, without Events, the add-on or a membership. */
function EventPayoutPage() {
  const params = useParams();
  const navigate = useNavigate();
  const space = useMakerspace();
  const base = `${space.slug ? `/m/${encodeURIComponent(space.slug)}` : ""}/member/event-payouts`;
  return <ProgrammeAccess slug={space.slug}>{user => params.obligationId
    ? <MemberPayoutDetail actorId={user.id} id={params.obligationId} />
    : <MemberPayoutHistory actorId={user.id} onOpen={id => navigate(`${base}/${id}`)} />}</ProgrammeAccess>;
}

/** "My prizes" (hack-money G3/G4/G6): this space's prizes for the signed-in member. */
function PrizesPage() {
  const space = useMakerspace();
  if (space.loading) return <p role="status">Loading…</p>;
  const makerspaceId = space.makerspaceId;
  if (!makerspaceId) return <p role="alert">Prizes are unavailable here.</p>;
  return <ProgrammeAccess slug={space.slug}>{user => <MyPrizes scope={{ makerspaceId, actorId: user.id }} />}</ProgrammeAccess>;
}

function addonKind(path: string): AddonKind {
  return path.includes("stage-responses") ? "response" : path.includes("stage-forms") ? "stages" : "reimbursement";
}

export function MemberEventAddonRoutes() {
  return <Routes>
    {eventAddonPaths.map(path => <Route key={path} path={path} element={<EventAddonPage kind={addonKind(path)} />} />)}
    {eventPayoutPaths.map(path => <Route key={path} path={path} element={<EventPayoutPage />} />)}
    {prizePaths.map(path => <Route key={path} path={path} element={<PrizesPage />} />)}
  </Routes>;
}
