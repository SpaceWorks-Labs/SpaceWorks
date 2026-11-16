import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { pageView } from "../lib/webAnalytics";

export function WebAnalytics() {
  const location = useLocation();
  useEffect(() => {
    pageView(new URL(`${location.pathname}${location.search}${location.hash}`, window.location.origin));
  }, [location.pathname, location.search, location.hash]);
  return null;
}
