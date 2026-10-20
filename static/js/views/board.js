import { data, jira } from "../api.js";
import { assign, planBatch, PROJECT } from "../system.js";
import { banner, date, esc, modal, person, priority, priorityOptions, status, toast } from "../ui.js";

function row(issue, reqs) {
  const f = issue.fields;
  const req = reqs[issue.key] ?? [];
  const reqCell = req.length
    ? `<span class="lozenge purple" title="${esc(req.map((r) => r.skill).join(", "))}">${req.length} prasības</span>`
    : `<span class="muted small">—</span>`;
  return `<tr>
    <td class="issue-key"><a href="#/issue/${esc(issue.key)}">${esc(issue.key)}</a></td>
    <td><a class="issue-link" href="#/issue/${esc(issue.key)}">${esc(f.summary)}</a></td>
    <td>${priority(f.priority.name)}</td>
    <td>${status(f.status.name)}</td>
    <td>${person(f.assignee?.displayName)}</td>
    <td class="num">${date(f.duedate)}</td>
    <td>${reqCell}</td>
  </tr>`;
}

function table(issues, reqs) {
  if (!issues.length) return `<div class="card empty">Nav uzdevumu</div>`;
  return `<div class="card table-wrap"><table class="table">
    <thead><tr><th>Atslēga</th><th>Nosaukums</th><th>Prioritāte</th><th>Statuss</th><th>Izpildītājs</th>
    <th>Termiņš</th><th>Sadale</th></tr></thead>
    <tbody>${issues.map((i) => row(i, reqs)).join("")}</tbody></table></div>`;
}

export default async function board(el, ...rest) {
  const isCurrent = rest.at(-1);
  const [{ issues }, reqs] = await Promise.all([jira.search(`project = ${PROJECT} ORDER BY key`), data.allRequirements()]);
  if (!isCurrent()) return;
  issues.sort((a, b) => Number(b.key.split("-")[1]) - Number(a.key.split("-")[1]));
  const open = issues.filter((i) => i.fields.status.statusCategory.key !== "done");
  const unassigned = open.filter((i) => !i.fields.assignee);
  const assigned = open.filter((i) => i.fields.assignee);
  const done = issues.filter((i) => i.fields.status.statusCategory.key === "done");

  el.innerHTML = `
    <div class="breadcrumbs">Projekti / Uzdevumu sadales sistēma</div>
    <div class="page-head">
      <div><h1>Uzdevumi</h1><p>Projekta DEV uzdevumi no Jira. Atveriet uzdevumu, lai norādītu prasības un saņemtu ieteikumu.</p></div>
      <div class="actions">
        <button class="btn" id="create">+ Izveidot uzdevumu</button>
        <button class="btn primary" id="batch" ${unassigned.length ? "" : "disabled"}>Sadalīt visus nepiešķirtos</button>
      </div>
    </div>
    <div class="section-title">Nepiešķirtie <span class="count">${unassigned.length}</span></div>
    ${table(unassigned, reqs)}
    <div class="section-title">Procesā un jādara <span class="count">${assigned.length}</span></div>
    ${table(assigned, reqs)}
    <details style="margin-top:24px"><summary class="section-title" style="display:list-item;cursor:pointer">
      Pabeigti <span class="count">${done.length}</span></summary>${table(done, reqs)}</details>`;

  el.querySelector("#create").onclick = () => createIssueDialog();
  el.querySelector("#batch").onclick = async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Aprēķina…`;
    try {
      await batchDialog();
    } finally {
      btn.disabled = false;
      btn.textContent = "Sadalīt visus nepiešķirtos";
    }
  };
}

function createIssueDialog() {
  const due = new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10);
  modal({
    title: "Izveidot uzdevumu",
    submit: "Izveidot",
    body: `
      <label class="field">Nosaukums *<input type="text" name="summary" maxlength="200" required></label>
      <label class="field">Apraksts<textarea name="description" rows="3"></textarea></label>
      <div class="form-grid">
        <label class="field">Prioritāte<select name="priority">${priorityOptions("Medium")}</select></label>
        <label class="field">Termiņš<input type="date" name="duedate" value="${due}"></label>
      </div>`,
    onSubmit: async (form) => {
      const f = Object.fromEntries(new FormData(form));
      if (!f.summary.trim()) { toast("Ievadiet nosaukumu", "warning"); return false; }
      try {
        const { key } = await jira.createIssue({
          project: { key: PROJECT }, summary: f.summary.trim(), description: f.description,
          priority: { name: f.priority }, duedate: f.duedate || null, issuetype: { name: "Uzdevums" },
        });
        toast(`Izveidots ${key}`, "success");
        location.hash = `#/issue/${key}`;
      } catch (err) {
        toast(err.message, "error");
        return false;
      }
    },
  });
}

async function batchDialog() {
  let plan;
  try {
    plan = await planBatch();
  } catch (err) {
    toast(err.message, err.kind === "warning" ? "warning" : "error", 6000);
    return;
  }
  const { issues, skipped, team, res } = plan;
  const names = Object.fromEntries(team.candidates.map((c) => [c.account_id, c.name]));
  const resultByKey = Object.fromEntries(res.results.map((r) => [r.key, r]));

  const rows = issues.map((i) => {
    const r = resultByKey[i.key];
    const acc = res.assignment[i.key];
    const pick = r.candidates.find((c) => c.account_id === acc);
    const best = r.candidates[0];
    const note = !acc
      ? (r.status === "no_candidates" ? "Nav atbilstošu kandidātu" : "Visi piemērotie jau aizņemti")
      : best && best.account_id !== acc ? `Labākais atsevišķi: ${esc(best.name)} (${best.score})` : "";
    return `<tr>
      <td><input type="checkbox" name="pick" value="${esc(i.key)}" ${acc ? "checked" : "disabled"}></td>
      <td class="issue-key">${esc(i.key)}</td><td>${esc(i.fields.summary)}</td><td>${priority(i.fields.priority.name)}</td>
      <td>${acc ? person(names[acc]) : `<span class="unassigned">—</span>`}</td>
      <td class="right num">${pick ? pick.score : "—"}</td>
      <td class="small muted">${note}</td></tr>`;
  }).join("");

  modal({
    title: "Sadalīt visus nepiešķirtos",
    wide: true,
    submit: "Apstiprināt atzīmētos",
    submitClass: "success",
    body: `
      <p class="muted" style="margin:0">Ungāru algoritms (SciPy <span class="mono">linear_sum_assignment</span>) atrada
      sadali ar lielāko kopējo vērtējumu, ņemot vērā uzdevumu prioritātes. Vienam darbiniekam ne vairāk kā
      ${plan.settings.max_new_per_candidate} jauns uzdevums. Kopējais vērtējums: <b class="num">${res.total_score}</b>.</p>
      ${skipped.length ? banner(`Izlaisti bez prasībām: ${skipped.map((s) => s.key).join(", ")}`, "warning") : ""}
      <div class="table-wrap"><table class="table">
        <thead><tr><th></th><th>Atslēga</th><th>Uzdevums</th><th>Prioritāte</th><th>Ieteiktais</th>
        <th class="right">Vērtējums</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`,
    onSubmit: async (form) => {
      const keys = [...form.querySelectorAll("[name=pick]:checked")].map((c) => c.value);
      let ok = 0;
      for (const key of keys) {
        const r = resultByKey[key];
        const chosen = r.candidates.find((c) => c.account_id === res.assignment[key]);
        try {
          await assign({
            issueKey: key, chosen, recommended: chosen, mode: "batch",
            scores: Object.fromEntries(r.candidates.map((c) => [c.account_id, c.score])),
          });
          ok += 1;
        } catch (err) {
          toast(`${key}: ${err.message}`, "error", 6000);
        }
      }
      if (ok) toast(`Piešķirti ${ok} uzdevumi, lēmumi saglabāti vēsturē`, "success");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    },
  });
}
