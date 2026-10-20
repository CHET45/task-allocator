import { data } from "../api.js";
import { confirmDialog, esc, modal, toast } from "../ui.js";

export default async function skillsView(el, ...rest) {
  const isCurrent = rest.at(-1);
  const skills = await data.skills();
  if (!isCurrent()) return;

  el.innerHTML = `
    <div class="page-head">
      <div><h1>Kvalifikāciju katalogs</h1>
        <p>Prasmes, ko var pieprasīt uzdevumiem un piešķirt darbiniekiem. Katalogs glabājas PostgreSQL;
        pēc katras izmaiņas tā kopija tiek atjaunota Forge Storage glabātuvē.</p></div>
      <div class="actions"><button class="btn primary" id="add">+ Jauna kvalifikācija</button></div>
    </div>
    <div class="card table-wrap"><table class="table">
      <thead><tr><th>Nosaukums</th><th>Kategorija</th><th>Apraksts</th><th class="right">Darbinieki</th><th></th></tr></thead>
      <tbody>${skills.map((s) => `<tr>
        <td><b>${esc(s.name)}</b></td><td>${esc(s.category)}</td><td class="muted">${esc(s.description)}</td>
        <td class="right num">${s.employees}</td>
        <td class="right" style="white-space:nowrap">
          <button class="btn subtle sm" data-edit="${s.id}">Labot</button>
          <button class="btn subtle sm" data-del="${s.id}">Dzēst</button></td></tr>`).join("")}
      </tbody></table></div>`;

  const rerender = () => skillsView(el, isCurrent);
  el.querySelector("#add").onclick = () => skillDialog(null, rerender);
  el.querySelectorAll("[data-edit]").forEach((b) => {
    b.onclick = () => skillDialog(skills.find((s) => s.id === Number(b.dataset.edit)), rerender);
  });
  el.querySelectorAll("[data-del]").forEach((b) => {
    b.onclick = async () => {
      const s = skills.find((x) => x.id === Number(b.dataset.del));
      if (!(await confirmDialog("Dzēst kvalifikāciju?", `“${s.name}” tiks izņemta no kataloga.`, "Dzēst", "danger"))) return;
      try {
        await data.deleteSkill(s.id);
        toast("Kvalifikācija dzēsta", "success");
        rerender();
      } catch (err) {
        toast(err.message, "error", 6000);
      }
    };
  });
}

function skillDialog(skill, done) {
  const categories = ["Programmēšana", "Saskarne", "Dati", "Infrastruktūra", "Kvalitāte", "Analīze"];
  modal({
    title: skill ? "Labot kvalifikāciju" : "Jauna kvalifikācija",
    body: `
      <label class="field">Nosaukums *<input type="text" name="name" value="${esc(skill?.name)}" maxlength="80"></label>
      <label class="field">Kategorija<input type="text" name="category" list="cats" value="${esc(skill?.category)}">
        <datalist id="cats">${categories.map((c) => `<option value="${c}">`).join("")}</datalist></label>
      <label class="field">Apraksts<textarea name="description" rows="2">${esc(skill?.description)}</textarea></label>`,
    onSubmit: async (form) => {
      const body = Object.fromEntries(new FormData(form));
      try {
        if (skill) await data.updateSkill(skill.id, body);
        else await data.createSkill(body);
        toast(skill ? "Saglabāts" : "Kvalifikācija pievienota katalogam", "success");
        done();
      } catch (err) {
        toast(err.message, "error");
        return false;
      }
    },
  });
}
