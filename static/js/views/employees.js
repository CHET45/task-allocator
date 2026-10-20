import { data, forge, jira } from "../api.js";
import { fetchWorkload, PROJECT } from "../system.js";
import { EMPLOYEE_STATUS, esc, level, modal, person, toast } from "../ui.js";

export default async function employeesView(el, ...rest) {
  const isCurrent = rest.at(-1);
  const [employees, skills, settings, users] = await Promise.all([
    data.employees(), data.skills(), forge.get("settings.project"), jira.assignableUsers(PROJECT),
  ]);
  const workload = await fetchWorkload(employees.map((e) => e.jira_account_id), null);
  if (!isCurrent()) return;
  const known = new Set(employees.map((e) => e.jira_account_id));
  const missing = users.filter((u) => !known.has(u.accountId));

  el.innerHTML = `
    <div class="page-head">
      <div><h1>Darbinieki un kvalifikācijas</h1>
        <p>Darbinieku profili sistēmas datubāzē. Noslodze tiek iegūta no Jira pieprasījuma brīdī.
        Darbinieku nedzēš, bet deaktivizē, lai saglabātu lēmumu vēsturi.</p></div>
      <div class="actions"><button class="btn" id="import" ${missing.length ? "" : "disabled"}>
        Importēt no Jira${missing.length ? ` (${missing.length})` : ""}</button></div>
    </div>
    <div class="card table-wrap"><table class="table">
      <thead><tr><th>Darbinieks</th><th>Komanda</th><th>Statuss</th><th>Kvalifikācijas</th><th>Noslodze</th><th></th></tr></thead>
      <tbody>${employees.map((e) => {
        const w = workload[e.jira_account_id];
        const over = w.priority_points > settings.workload_limit;
        return `<tr>
          <td>${person(e.display_name, "")}</td>
          <td>${esc(e.team) || `<span class="muted">—</span>`}</td>
          <td><select data-status="${e.id}">${Object.entries(EMPLOYEE_STATUS).map(([k, l]) =>
            `<option value="${k}" ${k === e.status ? "selected" : ""}>${l}</option>`).join("")}</select></td>
          <td><div class="chips">${e.skills.map((s) => `<span class="chip">${esc(s.name)} ${level(s.level)}</span>`).join("")
            || `<span class="muted small">nav kvalifikāciju</span>`}</div></td>
          <td class="num small" style="white-space:nowrap">${w.open_issues} uzd. ·
            <span class="${over ? "lozenge red" : ""}">${w.priority_points}/${settings.workload_limit} p.</span></td>
          <td class="right"><button class="btn sm" data-skills="${e.id}">Kvalifikācijas</button></td></tr>`;
      }).join("")}</tbody></table></div>`;

  const rerender = () => employeesView(el, isCurrent);
  el.querySelector("#import").onclick = async () => {
    const r = await data.importFromJira(missing);
    toast(`Importēti: ${r.added.join(", ")}`, "success");
    rerender();
  };
  el.querySelectorAll("[data-status]").forEach((s) => {
    s.onchange = async () => {
      try {
        await data.patchEmployee(Number(s.dataset.status), { status: s.value });
        toast("Statuss saglabāts", "success");
      } catch (err) {
        toast(err.message, "error");
      }
    };
  });
  el.querySelectorAll("[data-skills]").forEach((b) => {
    b.onclick = () => skillsDialog(employees.find((e) => e.id === Number(b.dataset.skills)), skills, rerender);
  });
}

// Decision table 5.1.2: the server answers missing data / duplicate / saved.
function skillsDialog(emp, catalog, done) {
  let current = emp;
  let changed = false;
  const body = () => `
    <div class="table-wrap"><table class="table"><thead><tr><th>Kvalifikācija</th><th>Līmenis</th><th></th></tr></thead>
      <tbody>${current.skills.map((s) => `<tr><td>${esc(s.name)}</td>
        <td><select data-level="${s.skill_id}">${[1, 2, 3, 4, 5].map((n) =>
          `<option ${n === s.level ? "selected" : ""}>${n}</option>`).join("")}</select></td>
        <td class="right"><button type="button" class="btn subtle sm" data-remove="${s.skill_id}">Noņemt</button></td></tr>`).join("")
        || `<tr><td colspan="3" class="muted">Nav kvalifikāciju</td></tr>`}</tbody></table></div>
    <div class="label small muted" style="font-weight:700">PIEŠĶIRT KVALIFIKĀCIJU</div>
    <div class="actions">
      <select name="skill" style="flex:1"><option value="">— kvalifikācija —</option>${catalog.map((s) =>
        `<option value="${s.id}">${esc(s.name)}</option>`).join("")}</select>
      <select name="level"><option value="">līmenis</option>${[1, 2, 3, 4, 5].map((n) => `<option>${n}</option>`).join("")}</select>
      <button type="button" class="btn primary" data-add>Piešķirt</button>
    </div>
    <div data-msg></div>`;

  const m = modal({
    title: `${emp.display_name}: kvalifikācijas`,
    submit: "Gatavs",
    body: body(),
    onSubmit: () => { if (changed) done(); },
    onOpen: (form) => wire(form),
  });

  function refresh(updated) {
    current = updated;
    changed = true;
    m.form.querySelector(".modal-body").innerHTML = body();
    wire(m.form);
  }

  function wire(form) {
    const msg = (text, kind) => {
      form.querySelector("[data-msg]").innerHTML = text ? `<div class="banner ${kind}"><div class="grow">${esc(text)}</div></div>` : "";
    };
    form.querySelector("[data-add]").onclick = async () => {
      const skillId = form.skill.value ? Number(form.skill.value) : null;
      const lvl = form.level.value ? Number(form.level.value) : null;
      try {
        refresh(await data.addEmployeeSkill(emp.id, skillId, lvl));
        msg("Kvalifikācija saglabāta", "success");
      } catch (err) {
        msg(err.message, "warning");
      }
    };
    form.querySelectorAll("[data-level]").forEach((s) => {
      s.onchange = async () => refresh(await data.setEmployeeSkill(emp.id, Number(s.dataset.level), Number(s.value)));
    });
    form.querySelectorAll("[data-remove]").forEach((b) => {
      b.onclick = async () => refresh(await data.removeEmployeeSkill(emp.id, Number(b.dataset.remove)));
    });
  }
}
