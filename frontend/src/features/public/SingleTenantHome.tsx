import { Navigate, useParams } from "react-router-dom";
import { useTenant } from "../../lib/tenant";
import { NotFoundPage } from "../NotFoundPage";

/** Directory cards use central URLs; a bound frontend admits only its own space alias. */
export function SingleTenantHome() {
  const tenant = useTenant();
  const { slug } = useParams();
  return slug === tenant.slug ? <Navigate replace to="/" /> : <NotFoundPage />;
}
