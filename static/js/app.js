import { data } from "./api.js";
import { banner, esc } from "./ui.js";
import board from "./views/board.js";
import dashboard from "./views/dashboard.js";
import employees from "./views/employees.js";
import history from "./views/history.js";
import issue from "./views/issue.js";
import settings from "./views/settings.js";
import skills from "./views/skills.js";

const routes = { board, issue, skills, employees, history, settings, dashboard };
const navFor = { issue: "board" };
const view = document.getElementById("view");
let renderToken = 0;

async function route() {
  const [name = "board", ...params] = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const page = routes[name] ?? board;
  const token = ++renderToken;
  document.querySelectorAll("[data-nav]").forEach((a) =>
    a.classList.toggle("active", a.dataset.nav === (navFor[name] ?? name)));
  view.innerHTML = `<div class="muted"><span class="spinner"></span> Ielādē…</div>`;
  try {
    await page(view, ...params.map(decodeURIComponent), () => token === renderToken);
  } catch (err) {
    console.error(err);
    if (token === renderToken) view.innerHTML = banner(`Neizdevās atvērt skatu: ${err.message}`, "error");
  }
  view.focus({ preventScroll: true });
}

async function ping() {
  const dot = document.getElementById("service-dot");
  try {
    const h = await data.health();
    dot.className = `service-dot ${h.algorithm === "ok" ? "ok" : "bad"}`;
    dot.title = `Aprēķinu serviss: ${h.algorithm === "ok" ? "pieejams" : "nav pieejams"} · datubāze: ${esc(h.database)}`;
  } catch {
    dot.className = "service-dot bad";
    dot.title = "Serveris nav sasniedzams";
  }
}

window.addEventListener("hashchange", route);
window.addEventListener("allocator:health", ping);
if (!location.hash) location.hash = "#/board";
route();
ping();
setInterval(ping, 15000);
