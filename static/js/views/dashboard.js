// Visual-only section: hard-coded numbers that show how the team overview would look.
import { banner } from "../ui.js";

const LOAD = [
  ["Roberts Zariņš", 19], ["Jānis Kalniņš", 9], ["Elīna Krūmiņa", 7], ["Anna Bērziņa", 7],
  ["Mārtiņš Liepiņš", 6], ["Kristīne Vītola", 3], ["Līga Ozola", 2], ["Edgars Pētersons", 0],
];
const WEEKS = [["36", 6, 5], ["37", 9, 7], ["38", 7, 6], ["39", 11, 9], ["40", 8, 7], ["41", 10, 8]];
const GAPS = [["Forge spraudņi", 0, 3], ["CI/CD", 1, 3], ["React", 2, 4], ["SQL / PostgreSQL", 3, 4]];

export default async function dashboard(el) {
  const limit = 12;
  el.innerHTML = `
    <div class="page-head"><div><h1>Komandas pārskats</h1>
      <p>Kopsavilkums par noslodzi, ieteikumu pieņemšanu un kvalifikāciju trūkumiem.</p></div></div>
    ${banner("Šī sadaļa prototipā ir tikai vizuāla — skaitļi ir iekodēti, lai parādītu, kā skatam būtu jāizskatās.", "warning")}
    <div class="kpis">
      <div class="card kpi"><div class="v">51</div><div class="l">Sadalīti uzdevumi (6 nedēļas)</div></div>
      <div class="card kpi"><div class="v">82%</div><div class="l">Ieteikums apstiprināts</div></div>
      <div class="card kpi"><div class="v">0,6 s</div><div class="l">Vidējais ieteikuma laiks</div></div>
      <div class="card kpi"><div class="v">1</div><div class="l">Pārslogots darbinieks</div></div>
    </div>
    <div class="grid-2">
      <div class="card card-pad"><h2>Noslodze (prioritātes punkti)</h2>
        ${LOAD.map(([n, p]) => `<div class="hbar"><span>${n}</span><div class="track">
          <div class="fill ${p > limit ? "over" : ""}" style="width:${Math.min(p / 20, 1) * 100}%"></div></div>
          <span class="num right">${p}</span></div>`).join("")}
        <div class="small muted">Robeža: ${limit} punkti</div></div>
      <div class="card card-pad"><h2>Ieteikumi pa nedēļām</h2>
        ${WEEKS.map(([w, total, ok]) => `<div class="hbar"><span>${w}. nedēļa</span><div class="track">
          <div class="fill" style="width:${total / 12 * 100}%;background:linear-gradient(90deg,#22a06b ${ok / total * 100}%,#cfe1fd 0)"></div></div>
          <span class="num right">${ok}/${total}</span></div>`).join("")}
        <div class="small muted">Zaļš — apstiprināti ieteikumi, gaišs — izvēlēts cits</div></div>
      <div class="card card-pad"><h2>Kvalifikāciju trūkumi</h2>
        <table class="table"><thead><tr><th>Kvalifikācija</th><th class="right">Ir</th><th class="right">Vajag</th></tr></thead>
        <tbody>${GAPS.map(([s, have, need]) => `<tr><td>${s}</td><td class="right num">${have}</td>
          <td class="right num"><span class="lozenge ${have === 0 ? "red" : "yellow"}">${need}</span></td></tr>`).join("")}</tbody></table></div>
      <div class="card card-pad"><h2>Integrācijas</h2>
        <table class="table"><tbody>
          <tr><td>Jira Cloud REST API</td><td><span class="lozenge green">savienots</span></td></tr>
          <tr><td>Aprēķinu serviss (FastAPI)</td><td><span class="lozenge green">/health OK</span></td></tr>
          <tr><td>PostgreSQL</td><td><span class="lozenge green">OK</span></td></tr>
          <tr><td>GitLab CI/CD</td><td><span class="lozenge green">pēdējais konveijers veiksmīgs</span></td></tr>
        </tbody></table></div>
    </div>`;
}
