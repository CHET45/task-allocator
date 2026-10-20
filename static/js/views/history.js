import { data } from "../api.js";
import { dateTime, esc, person } from "../ui.js";

let tab = "decisions";

export default async function historyView(el, ...rest) {
  const isCurrent = rest.at(-1);
  const [decisions, audit] = await Promise.all([data.decisions(), data.audit()]);
  if (!isCurrent()) return;
  const followed = decisions.filter((d) => d.followed_recommendation).length;
  const scored = decisions.filter((d) => d.recommended_account_id);
  const rate = scored.length ? Math.round(followed / scored.length * 100) : 0;

  el.innerHTML = `
    <div class="page-head"><div><h1>Lēmumu vēsture</h1>
      <p>Katrs piešķīrums: sistēmas ieteikums, vadītāja gala izvēle, vērtējumi un laiks (tabula Assignment_Decisions).</p></div></div>
    <div class="kpis">
      <div class="card kpi"><div class="v">${decisions.length}</div><div class="l">Lēmumi kopā</div></div>
      <div class="card kpi"><div class="v">${rate}%</div><div class="l">Ieteikums apstiprināts</div></div>
      <div class="card kpi"><div class="v">${scored.length - followed}</div><div class="l">Izvēlēts cits darbinieks</div></div>
      <div class="card kpi"><div class="v">${decisions.filter((d) => d.mode === "manual").length}</div><div class="l">Manuāli piešķirti</div></div>
    </div>
    <div class="tabs"><button data-tab="decisions">Lēmumi</button><button data-tab="audit">Audita žurnāls</button></div>
    <div id="tab-body"></div>`;

  const body = el.querySelector("#tab-body");
  const show = () => {
    el.querySelectorAll("[data-tab]").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    body.innerHTML = tab === "decisions" ? decisionsTable(decisions) : auditTable(audit);
  };
  el.querySelectorAll("[data-tab]").forEach((b) => { b.onclick = () => { tab = b.dataset.tab; show(); }; });
  show();
}

function decisionsTable(rows) {
  if (!rows.length) return `<div class="card empty">Lēmumu vēl nav. Piešķiriet uzdevumu uzdevuma skatā.</div>`;
  return `<div class="card table-wrap"><table class="table">
    <thead><tr><th>Laiks</th><th>Uzdevums</th><th>Ieteiktais</th><th>Gala izvēle</th><th>Rezultāts</th><th>Iemesls</th><th>Režīms</th></tr></thead>
    <tbody>${rows.map((d) => `<tr>
      <td class="num small">${dateTime(d.created_at)}</td>
      <td class="issue-key"><a href="#/issue/${esc(d.issue_key)}">${esc(d.issue_key)}</a></td>
      <td>${d.recommended ? `${person(d.recommended)} <span class="muted num">${d.recommended_score ?? ""}</span>` :
        `<span class="muted">—</span>`}</td>
      <td>${person(d.chosen)} <span class="muted num">${d.chosen_score ?? ""}</span></td>
      <td>${d.followed_recommendation ? `<span class="lozenge green">apstiprināts</span>` :
        d.recommended ? `<span class="lozenge blue">mainīts</span>` : `<span class="lozenge yellow">bez ieteikuma</span>`}</td>
      <td class="small">${esc(d.reason) || `<span class="muted">—</span>`}</td>
      <td class="small muted">${{ single: "viens", batch: "visi kopā", manual: "manuāli" }[d.mode] ?? esc(d.mode)}</td>
    </tr>`).join("")}</tbody></table></div>`;
}

function auditTable(rows) {
  if (!rows.length) return `<div class="card empty">Audita ierakstu nav</div>`;
  return `<div class="card table-wrap"><table class="table">
    <thead><tr><th>Laiks</th><th>Kas</th><th>Darbība</th><th>Objekts</th><th>Detaļas</th></tr></thead>
    <tbody>${rows.map((a) => `<tr><td class="num small">${dateTime(a.created_at)}</td><td>${esc(a.actor)}</td>
      <td class="mono">${esc(a.action)}</td><td class="mono">${esc(a.entity)}</td><td class="small">${esc(a.details)}</td></tr>`)
      .join("")}</tbody></table></div>`;
}
