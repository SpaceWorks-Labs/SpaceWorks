// Pre-paint boot code, loaded synchronously from <head> so the saved dark theme applies before first
// paint. It lives in a file, not an inline <script>, so the deployment CSP never needs 'unsafe-inline'
// or a hash (frontend/docker-entrypoint.d/40-web-analytics.sh).
(function () {
  try {
    var p = localStorage.getItem("makerspace.theme");
    var dark = p === "dark" || (p === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    if (dark) document.documentElement.classList.add("dark");
    var m = document.querySelector('meta[name="theme-color"]'); if (m && dark) m.setAttribute("content", "#000000");
  } catch (e) {}
})();
// Failsafe: if the app never mounts (script blocked or failed), do not leave the splash up forever.
setTimeout(function () { var s = document.getElementById("sw-splash"); var r = document.getElementById("root"); if (s && r && r.childElementCount === 0) s.style.display = "none"; }, 20000);
