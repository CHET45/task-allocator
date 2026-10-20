// Small rendering helpers shared by the views.

export const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));

export const PRIORITIES = [
  ["Highest", "Augstākā", "⇈"], ["High", "Augsta", "↑"], ["Medium", "Vidēja", "="],
  ["Low", "Zema", "↓"], ["Lowest", "Zemākā", "⇊"],
];
const PRIO = Object.fromEntries(PRIORITIES.map(([k, l, i]) => [k, { label: l, icon: i }]));

export const priority = (p) =>
  `<span class="prio prio-${esc(p)}"><i>${PRIO[p]?.icon ?? "="}</i>${esc(PRIO[p]?.label ?? p)}</span>`;

export const priorityOptions = (selected) => PRIORITIES
  .map(([k, l]) => `<option value="${k}" ${k === selected ? "selected" : ""}>${l}</option>`).join("");

export function status(name) {
  const cls = { "Jādara": "", "Procesā": "blue", "Pabeigts": "green" }[name] ?? "";
  return `<span class="lozenge ${cls}">${esc(name)}</span>`;
}

export const EMPLOYEE_STATUS = { active: "Aktīvs", on_leave: "Atvaļinājumā", inactive: "Deaktivizēts" };

const AV_COLORS = ["#0c66e4", "#1f845a", "#5e4db2", "#c9372c", "#a54800", "#227d9b", "#943d73", "#6a9a23"];
export function initials(name) {
  return String(name).split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
}
export function avatar(name, size = "") {
  let h = 0;
  for (const ch of String(name)) h = (h * 31 + ch.codePointAt(0)) >>> 0;
  return `<span class="avatar ${size}" style="--av:${AV_COLORS[h % AV_COLORS.length]}">${esc(initials(name))}</span>`;
}
export const person = (name, size = "avatar-sm") =>
  name ? `<span class="person">${avatar(name, size)}${esc(name)}</span>` : `<span class="unassigned">Nav piešķirts</span>`;

export const level = (n) =>
  `<span class="level" title="Līmenis ${n}/5">${[1, 2, 3, 4, 5].map((i) => `<span class="${i <= n ? "on" : ""}"></span>`).join("")}</span>`;

export function date(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("lv-LV", { day: "2-digit", month: "2-digit", year: "numeric" });
}
export function dateTime(iso) {
  return new Date(iso).toLocaleString("lv-LV", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function toast(message, kind = "info", ms = 4000) {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = message;
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), ms);
}

export function banner(message, kind = "info", extra = "") {
  return `<div class="banner ${kind}"><div class="grow">${esc(message)}</div>${extra}</div>`;
}

// Opens a modal; `onSubmit(form)` may return false to keep it open.
export function modal({ title, body, submit = "Saglabāt", submitClass = "primary", wide = false, onSubmit, onOpen }) {
  const root = document.getElementById("modal-root");
  root.innerHTML = `
    <div class="modal-back">
      <form class="modal ${wide ? "wide" : ""}" novalidate>
        <div class="modal-head"><h2>${esc(title)}</h2></div>
        <div class="modal-body">${body}</div>
        <div class="modal-foot">
          <button type="button" class="btn subtle" data-close>Atcelt</button>
          ${submit ? `<button type="submit" class="btn ${submitClass}">${esc(submit)}</button>` : ""}
        </div>
      </form>
    </div>`;
  const form = root.querySelector("form");
  const close = () => { root.innerHTML = ""; document.removeEventListener("keydown", onKey); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  root.querySelector("[data-close]").onclick = close;
  root.querySelector(".modal-back").addEventListener("mousedown", (e) => { if (e.target.classList.contains("modal-back")) close(); });
  form.onsubmit = async (e) => {
    e.preventDefault();
    const btn = form.querySelector("[type=submit]");
    if (btn) btn.disabled = true;
    try {
      if ((await onSubmit?.(form)) !== false) close();
    } finally {
      if (btn) btn.disabled = false;
    }
  };
  onOpen?.(form);
  form.querySelector("input, select, textarea")?.focus();
  return { close, form };
}

export function confirmDialog(title, text, submit = "Apstiprināt", submitClass = "primary") {
  return new Promise((resolve) => {
    let ok = false;
    const m = modal({ title, body: `<p>${esc(text)}</p>`, submit, submitClass, onSubmit: () => { ok = true; } });
    const observer = new MutationObserver(() => {
      if (!document.body.contains(m.form)) { observer.disconnect(); resolve(ok); }
    });
    observer.observe(document.getElementById("modal-root"), { childList: true });
  });
}
