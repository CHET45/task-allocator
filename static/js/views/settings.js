import { data, forge } from "../api.js";
import { banner, confirmDialog, esc, toast } from "../ui.js";

const WEIGHTS = [
  ["skills", "Kvalifikāciju atbilstība", "Cik labi darbinieka līmeņi sedz prasības"],
  ["workload", "Pašreizējā noslodze", "Atvērto uzdevumu prioritātes punkti pret robežu"],
  ["priority", "Citi augstas prioritātes darbi", "Vienlaicīgi Augsta/Augstākā prioritātes uzdevumi"],
  ["deadline", "Tuvojošies termiņi", "Uzdevumi ar termiņu 7 dienu laikā"],
];

export default async function settingsView(el, ...rest) {
  const isCurrent = rest.at(-1);
  const [weights, settings] = await Promise.all([forge.get("weights.config"), forge.get("settings.project")]);
  if (!isCurrent()) return;

  el.innerHTML = `
    <div class="page-head"><div><h1>Iestatījumi</h1>
      <p>Projekta administratoram. Vērtības glabājas Forge Storage (<span class="mono">weights.config</span>,
      <span class="mono">settings.project</span>); svaru maiņai nav vajadzīgas koda izmaiņas.</p></div></div>
    <div class="stack" style="max-width:860px">
      <div class="card card-pad">
        <h2>Sadales faktoru svari</h2>
        <div class="weights">${WEIGHTS.map(([k, l, d]) => `
          <div><b>${l}</b><div class="small muted">${d}</div></div>
          <input type="range" min="0" max="100" step="5" data-w="${k}" value="${Math.round(weights[k] * 100)}">
          <div class="num" data-pct="${k}"></div>`).join("")}</div>
        <p class="small muted">Svari tiek normalizēti — procenti rāda faktora daļu kopējā vērtējumā.</p>
      </div>
      <div class="card card-pad">
        <h2>Projekta iestatījumi</h2>
        <div class="form-grid">
          <label class="field">Noslodzes robeža (prioritātes punkti)<input type="number" min="1" max="100" name="workload_limit" value="${esc(settings.workload_limit)}"></label>
          <label class="field">Rādīt kandidātus<input type="number" min="1" max="50" name="top_n" value="${esc(settings.top_n)}"></label>
          <label class="field">Aprēķinu servisa noildze (ms)<input type="number" min="200" max="30000" step="100" name="timeout_ms" value="${esc(settings.timeout_ms)}"></label>
          <label class="field">Jauni uzdevumi vienam (“Sadalīt visus”)<input type="number" min="1" max="10" name="max_new_per_candidate" value="${esc(settings.max_new_per_candidate)}"></label>
        </div>
        <div style="margin-top:16px" class="stack">
          <label class="switch"><input type="checkbox" name="enabled" ${settings.enabled ? "checked" : ""}> Sadale projektā ieslēgta</label>
        </div>
      </div>
      <div class="actions"><button class="btn primary" id="save">Saglabāt iestatījumus</button></div>

      <div class="card card-pad">
        <h2>Demonstrācijai</h2>
        ${banner("Šie slēdži ir tikai prototipa demonstrācijai, īstajā sistēmā to nebūtu.", "warning")}
        <div class="stack">
          <label class="switch"><input type="checkbox" id="outage" ${settings.demo_algorithm_outage ? "checked" : ""}>
            Simulēt aprēķinu servisa nepieejamību (pārbauda manuālās izvēles režīmu, lēmumu tabula 5.1.4)</label>
          <div><button class="btn danger" id="reset">Atjaunot demonstrācijas datus</button>
            <span class="small muted">Datubāze, Jira dati un iestatījumi tiek atgriezti sākuma stāvoklī.</span></div>
        </div>
      </div>
    </div>`;

  const sliders = [...el.querySelectorAll("[data-w]")];
  const updatePct = () => {
    const total = sliders.reduce((a, s) => a + Number(s.value), 0) || 1;
    sliders.forEach((s) => { el.querySelector(`[data-pct="${s.dataset.w}"]`).textContent = `${Math.round(s.value / total * 100)}%`; });
  };
  sliders.forEach((s) => { s.oninput = updatePct; });
  updatePct();

  el.querySelector("#save").onclick = async () => {
    const w = Object.fromEntries(sliders.map((s) => [s.dataset.w, Number(s.value) / 100]));
    const num = (n) => Number(el.querySelector(`[name=${n}]`).value);
    try {
      await forge.set("weights.config", w);
      await forge.set("settings.project", {
        workload_limit: num("workload_limit"), top_n: num("top_n"), timeout_ms: num("timeout_ms"),
        max_new_per_candidate: num("max_new_per_candidate"), enabled: el.querySelector("[name=enabled]").checked,
      });
      toast("Iestatījumi saglabāti Forge Storage", "success");
    } catch (err) {
      toast(err.message, "error");
    }
  };
  el.querySelector("#outage").onchange = async (e) => {
    await forge.set("settings.project", { demo_algorithm_outage: e.target.checked });
    window.dispatchEvent(new Event("allocator:health"));
    toast(e.target.checked ? "Aprēķinu serviss “izslēgts”" : "Aprēķinu serviss atkal pieejams", "warning");
  };
  el.querySelector("#reset").onclick = async () => {
    if (!(await confirmDialog("Atjaunot demonstrācijas datus?", "Visas izmaiņas tiks dzēstas.", "Atjaunot", "danger"))) return;
    await data.reset();
    window.dispatchEvent(new Event("allocator:health"));
    toast("Demonstrācijas dati atjaunoti", "success");
    settingsView(el, isCurrent);
  };
}
