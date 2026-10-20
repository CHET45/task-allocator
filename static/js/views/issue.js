import { data, forge, jira } from "../api.js";
import { assign, findCandidates, validateRequirements } from "../system.js";
import {
  avatar, banner, date, dateTime, esc, modal, person, priority, priorityOptions, status, toast,
} from "../ui.js";

const FACTORS = [
  ["skills", "Kvalifikācijas"], ["workload", "Noslodze"], ["priority", "Citi svarīgi darbi"], ["deadline", "Termiņi"],
];
let flash = null; // message shown once after the view re-renders

export default async function issueView(el, key, isCurrent) {
  const [issue, { requirements }, catalog, history] = await Promise.all([
    jira.issue(key), data.requirements(key), forge.get("skills.catalog"), data.decisions(key),
  ]);
  if (!isCurrent()) return;
  const f = issue.fields;
  const state = {
    priority: f.priority.name,
    rows: requirements.map((r) => ({ skill_id: r.skill_id, required: r.required, min_level: r.min_level })),
    dirty: false,
    picking: false,
    run: null,
  };

  el.innerHTML = `
    <div class="breadcrumbs"><a href="#/board">Projekti / Uzdevumu sadales sistēma</a> / ${esc(key)}</div>
    <div class="issue-grid">
      <div>
        <h1 class="issue-title">${esc(f.summary)}</h1>
        <p class="issue-desc">${esc(f.description) || `<span class="muted">Nav apraksta</span>`}</p>
        <section class="plugin" aria-label="Uzdevumu sadale">
          <div class="plugin-head"><span class="plugin-icon"></span><strong>Uzdevumu sadale</strong>
            <span class="app-tag">Forge lietotne</span>
            <span class="muted small" style="margin-left:auto">Kataloga versija ${esc(catalog.version)}</span></div>
          <div class="plugin-body">
            <div id="notice"></div>
            <div class="plugin-section">
              <div class="label">Uzdevuma prasības</div>
              <div class="actions">
                <label class="field" style="flex-direction:row;align-items:center;gap:8px">Prioritāte
                  <select id="prio"><option value="">— izvēlieties —</option>${priorityOptions(state.priority)}</select></label>
              </div>
              <div id="req-rows"></div>
              <div class="actions">
                <button class="btn subtle sm" id="add-req">+ Pievienot kvalifikāciju</button>
                <span style="flex:1"></span>
                <button class="btn" id="save-req">Saglabāt prasības</button>
                <button class="btn primary" id="search">Meklēt kandidātus</button>
              </div>
            </div>
            <div id="results"></div>
          </div>
        </section>
      </div>
      <aside class="stack">
        <div class="details">
          <div class="details-head">Informācija</div>
          <dl>
            <dt>Statuss</dt><dd>${status(f.status.name)}</dd>
            <dt>Izpildītājs</dt><dd id="assignee">${person(f.assignee?.displayName)}</dd>
            <dt>Prioritāte</dt><dd>${priority(f.priority.name)}</dd>
            <dt>Termiņš</dt><dd class="num">${date(f.duedate)}</dd>
            <dt>Izveidots</dt><dd class="num">${date(f.created)}</dd>
            <dt>Atslēga</dt><dd class="mono">${esc(key)}</dd>
          </dl>
        </div>
        <div class="details">
          <div class="details-head">Sadales vēsture</div>
          <div style="padding:10px 14px">${historyList(history)}</div>
        </div>
      </aside>
    </div>`;

  const $ = (s) => el.querySelector(s);
  const catalogIds = new Set(catalog.items.map((s) => s.id));
  const notice = (msg, kind = "info") => { $("#notice").innerHTML = msg ? banner(msg, kind) : ""; };

  if (flash) { notice(flash.message, flash.kind); flash = null; }

  function renderRows() {
    const groups = {};
    for (const s of catalog.items) (groups[s.category || "Citas"] ??= []).push(s);
    const options = (sel) => `<option value="">— kvalifikācija —</option>` + Object.entries(groups).map(([g, items]) =>
      `<optgroup label="${esc(g)}">${items.map((s) =>
        `<option value="${s.id}" ${s.id === sel ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</optgroup>`).join("");
    $("#req-rows").innerHTML = state.rows.length ? `
      <div class="req-row req-head"><span>Kvalifikācija</span><span>Veids</span><span>Min. līmenis</span><span></span></div>
      ${state.rows.map((r, i) => `<div class="req-row" data-i="${i}">
        <select data-k="skill_id">${options(r.skill_id)}</select>
        <select data-k="required"><option value="1" ${r.required ? "selected" : ""}>Obligāta</option>
          <option value="0" ${r.required ? "" : "selected"}>Vēlama</option></select>
        <select data-k="min_level">${[1, 2, 3, 4, 5].map((n) =>
          `<option ${n === r.min_level ? "selected" : ""}>${n}</option>`).join("")}</select>
        <button class="btn subtle icon" data-remove title="Noņemt">×</button></div>`).join("")}`
      : `<div class="muted small">Prasības vēl nav norādītas.</div>`;
  }
  renderRows();

  $("#req-rows").addEventListener("change", (e) => {
    const row = e.target.closest("[data-i]");
    if (!row) return;
    const r = state.rows[row.dataset.i];
    const k = e.target.dataset.k;
    r[k] = k === "required" ? e.target.value === "1" : Number(e.target.value) || null;
    state.dirty = true;
  });
  $("#req-rows").addEventListener("click", (e) => {
    if (!e.target.matches("[data-remove]")) return;
    state.rows.splice(e.target.closest("[data-i]").dataset.i, 1);
    state.dirty = true;
    renderRows();
  });
  $("#add-req").onclick = () => {
    state.rows.push({ skill_id: null, required: true, min_level: 3 });
    state.dirty = true;
    renderRows();
  };
  $("#prio").onchange = (e) => { state.priority = e.target.value; state.dirty = true; };

  async function saveRequirements() {
    const rows = state.rows.filter((r) => r.skill_id !== null);
    const problem = validateRequirements(state.priority, rows, catalogIds);
    if (problem) { notice(problem, "warning"); return false; }
    try {
      await data.saveRequirements(key, state.priority, rows);
      if (state.priority !== f.priority.name) {
        await jira.updateIssue(key, { priority: { name: state.priority } });
        f.priority.name = state.priority;
      }
      state.rows = rows;
      state.dirty = false;
      renderRows();
      return true;
    } catch (err) {
      notice(err.message, "warning");
      return false;
    }
  }

  $("#save-req").onclick = async () => {
    if (await saveRequirements()) { notice("Prasības saglabātas", "success"); }
  };

  $("#search").onclick = async () => {
    notice("");
    if (state.dirty && !(await saveRequirements())) return;
    if (!state.rows.length) { notice("Norādiet vismaz vienu obligāto kvalifikāciju", "warning"); return; }
    const done = new Set();
    const steps = () => `<div class="plugin-section"><div class="steps">${[
      ["validated", "Datu validācija"], ["jira", "Jira dati un noslodze (JQL)"], ["scored", "Aprēķinu serviss"],
    ].map(([k, l]) => `<span class="${done.has(k) ? "done" : ""}">${done.has(k) ? "✓" : "…"} ${l}</span>`).join("")}</div>
      <div class="muted"><span class="spinner"></span> Meklē kandidātus…</div></div>`;
    state.run = null;
    $("#results").innerHTML = steps();
    $("#search").disabled = true;
    try {
      state.run = await findCandidates(key, (s) => { done.add(s); if (!state.run) $("#results").innerHTML = steps(); });
      state.picking = false;
      renderResults();
    } catch (err) {
      $("#results").innerHTML = "";
      notice(err.message, err.kind === "warning" ? "warning" : "error");
    } finally {
      $("#search").disabled = false;
      window.dispatchEvent(new Event("allocator:health"));
    }
  };

  function renderResults() {
    const run = state.run;
    if (run.mode === "manual") return renderManual(run);
    const r = run.result;
    const byAcc = Object.fromEntries(run.team.candidates.map((c) => [c.account_id, c]));
    const excluded = r.excluded.length ? `<details class="excluded"><summary>Izslēgti ${r.excluded.length} kandidāti</summary>
      <ul>${r.excluded.map((x) => `<li><b>${esc(x.name)}</b> — ${esc(x.reason)}${byAcc[x.account_id]?.has_profile
        ? "" : " · <i>nav profila sistēmā</i>"}</li>`).join("")}</ul></details>` : "";

    if (r.status === "no_candidates") {
      $("#results").innerHTML = banner("Nav atbilstošu kandidātu", "warning") + `
        <p class="muted small" style="margin:0">Neviens darbinieks neatbilst obligātajām prasībām. Mainiet prasības vai
        piešķiriet uzdevumu manuāli.</p>${excluded}
        <div class="actions"><button class="btn" id="manual">Piešķirt manuāli</button></div>`;
      $("#manual").onclick = () => manualPick(run.team.candidates, null, r);
      return;
    }

    const best = r.candidates.find((c) => c.account_id === r.recommended) ?? r.candidates[0];
    const current = run.issue.fields.assignee;
    $("#results").innerHTML = `
      <div class="plugin-section">
        <div class="label">Ieteikums</div>
        ${current ? banner(`Pašreizējais izpildītājs: ${current.displayName}. Apstiprinot uzdevums tiks pārpiešķirts.`) : ""}
        <div class="reco">
          ${avatar(best.name, "avatar-lg")}
          <div><div class="reco-name">${esc(best.name)}</div>
            <ul class="reco-why">${best.explanation.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
          <div class="score-big">${best.score}<small>no 100</small></div>
        </div>
        <div class="actions">
          <button class="btn success" id="approve">Apstiprināt</button>
          <button class="btn" id="other">${state.picking ? "Atcelt izvēli" : "Izvēlēties citu"}</button>
        </div>
      </div>
      <div class="plugin-section">
        <div class="label">Kandidāti (${r.candidates.length})</div>
        <div class="legend">${FACTORS.map(([k, l]) => `<span><i class="f-${k}" style="background:${{
          skills: "#1d7afc", workload: "#22a06b", priority: "#e2b203", deadline: "#8f7ee7" }[k]}"></i>${l}
          ${Math.round(run.weights[k] * 100 / Object.values(run.weights).reduce((a, b) => a + b, 0))}%</span>`).join("")}</div>
        <div class="table-wrap"><table class="table">
          <thead><tr><th>#</th><th>Darbinieks</th><th>Vērtējums</th><th>Noslodze</th><th>Pamatojums</th>
          ${state.picking ? "<th></th>" : ""}</tr></thead>
          <tbody>${r.candidates.map((c, i) => {
            const wl = byAcc[c.account_id].workload;
            return `<tr class="${c.account_id === best.account_id ? "is-reco" : ""}">
              <td class="num">${i + 1}</td>
              <td>${person(c.name)}</td>
              <td><div style="display:flex;align-items:center;gap:8px">
                <div class="bar" title="${FACTORS.map(([k, l]) => `${l}: +${c.contributions[k]}`).join(" · ")}${
                  c.penalty ? ` · sods −${c.penalty}` : ""}">
                  ${FACTORS.map(([k]) => `<span class="f-${k}" style="width:${c.contributions[k]}%"></span>`).join("")}</div>
                <b class="num">${c.score}</b></div></td>
              <td class="small num nowrap">${wl.open_issues} uzd. · ${wl.priority_points}/${run.settings.workload_limit} p.</td>
              <td><ul class="why-list">${c.explanation.slice(1).filter((x) => !x.startsWith("Noslodze:")).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></td>
              ${state.picking ? `<td>${c.account_id === best.account_id ? "" :
                `<button class="btn sm" data-pick="${esc(c.account_id)}">Izvēlēties</button>`}</td>` : ""}
            </tr>`;
          }).join("")}</tbody></table></div>
        ${excluded}
        <div class="muted small">Noslodze iegūta no Jira ${run.team.takenAt.toLocaleTimeString("lv-LV")} ·
          Ungāru algoritms · API v1</div>
      </div>`;

    const scores = Object.fromEntries(r.candidates.map((c) => [c.account_id, c.score]));
    $("#approve").onclick = () => doAssign({ chosen: best, recommended: best, scores });
    $("#other").onclick = () => { state.picking = !state.picking; renderResults(); };
    el.querySelectorAll("[data-pick]").forEach((b) => {
      b.onclick = () => overrideDialog(r.candidates.find((c) => c.account_id === b.dataset.pick), best, scores);
    });
  }

  function renderManual(run) {
    $("#results").innerHTML = banner(`${run.error}. Kandidātu saraksts bez vērtējuma — izvēlieties darbinieku manuāli.`,
      "error") + candidateTableNoScore(run.team.candidates, run.settings);
    el.querySelectorAll("[data-manual]").forEach((b) => {
      b.onclick = () => {
        const c = run.team.candidates.find((x) => x.account_id === b.dataset.manual);
        doAssign({ chosen: c, recommended: null, scores: {}, mode: "manual" });
      };
    });
  }

  function manualPick(candidates, recommended, result) {
    modal({
      title: "Piešķirt manuāli",
      wide: true,
      submit: null,
      body: `<p class="muted" style="margin:0">Neviens neatbilst obligātajām prasībām. Izvēle tiks saglabāta lēmumu vēsturē.</p>
        ${candidateTableNoScore(candidates, state.run.settings)}`,
      onOpen: (form) => form.querySelectorAll("[data-manual]").forEach((b) => {
        b.onclick = () => {
          document.getElementById("modal-root").innerHTML = "";
          const c = candidates.find((x) => x.account_id === b.dataset.manual);
          doAssign({ chosen: c, recommended, scores: {}, mode: "manual",
            reason: "Nav kandidātu, kas atbilst obligātajām prasībām" });
        };
      }),
    });
  }

  function overrideDialog(chosen, best, scores) {
    modal({
      title: `Piešķirt: ${chosen.name}`,
      submit: "Piešķirt",
      body: `<p style="margin:0">Sistēma ieteica <b>${esc(best.name)}</b> (${best.score}). Jūs izvēlaties
        <b>${esc(chosen.name)}</b> (${chosen.score}).</p>
        <label class="field">Iemesls (tiks saglabāts lēmumu vēsturē) *
          <textarea name="reason" rows="3" placeholder="Piemēram: jāapgūst šī sistēmas daļa"></textarea></label>`,
      onSubmit: async (form) => {
        const reason = form.reason.value.trim();
        if (!reason) { toast("Norādiet iemeslu", "warning"); return false; }
        return doAssign({ chosen, recommended: best, scores, reason });
      },
    });
  }

  async function doAssign(args) {
    try {
      const d = await assign({ issueKey: key, ...args });
      flash = {
        kind: "success",
        message: `${key} piešķirts: ${d.chosen}. ${d.followed_recommendation ? "Ieteikums apstiprināts." :
          "Izvēlēts cits darbinieks."} Lēmums saglabāts vēsturē.`,
      };
      issueView(el, key, isCurrent);
      return true;
    } catch (err) {
      toast(err.message, "error", 7000);
      return false;
    }
  }
}

function candidateTableNoScore(candidates, settings) {
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Darbinieks</th><th>Kvalifikācijas</th>
    <th>Noslodze</th><th></th></tr></thead><tbody>${candidates.map((c) => `<tr>
      <td>${person(c.name)}${c.available ? "" : ` <span class="lozenge yellow">nav pieejams</span>`}</td>
      <td><div class="chips">${Object.entries(c.skills).map(([n, l]) => `<span class="chip">${esc(n)} <b>${l}</b></span>`)
        .join("") || `<span class="muted small">nav profila</span>`}</div></td>
      <td class="small num">${c.workload.open_issues} uzd. · ${c.workload.priority_points}/${settings.workload_limit} p.</td>
      <td><button class="btn sm" data-manual="${esc(c.account_id)}">Piešķirt</button></td></tr>`).join("")}
    </tbody></table></div>`;
}

function historyList(items) {
  if (!items.length) return `<div class="muted small">Sadales lēmumu vēl nav.</div>`;
  return items.map((d) => `<div style="padding:6px 0;border-bottom:1px solid var(--border)">
    <div class="small muted">${dateTime(d.created_at)} · ${esc(d.manager)}</div>
    <div>${d.followed_recommendation ? `<span class="lozenge green">ieteikums</span>` :
      d.mode === "manual" ? `<span class="lozenge yellow">manuāli</span>` : `<span class="lozenge blue">cits</span>`}
      → <b>${esc(d.chosen)}</b>${d.chosen_score != null ? ` <span class="muted num">(${d.chosen_score})</span>` : ""}</div>
    ${d.reason ? `<div class="small muted">${esc(d.reason)}</div>` : ""}</div>`).join("");
}
