// System module (architecture 2.1): coordinates the allocation flow on the Forge side.
// validation -> Jira data -> workload (JQL) -> normalisation -> algorithm call -> assignment -> decision log.
import { algorithm, ApiError, data, forge, jira } from "./api.js";

export const PROJECT = "DEV";
export const MANAGER = "Vadītājs (demo)";
const PRIORITY_POINTS = { Highest: 5, High: 4, Medium: 3, Low: 2, Lowest: 1 };
const DUE_SOON_DAYS = 7;

export class FlowError extends Error {
  constructor(message, kind = "error") {
    super(message);
    this.kind = kind;
  }
}

function daysUntil(isoDate) {
  const today = new Date(new Date().toDateString());
  return Math.round((new Date(isoDate) - today) / 86400000);
}

// One JQL request for the whole team instead of one per person (architecture 6.1).
export async function fetchWorkload(accountIds, excludeKey) {
  const workload = Object.fromEntries(accountIds.map((id) => [id, {
    open_issues: 0, priority_points: 0, high_priority_open: 0, due_soon_open: 0,
  }]));
  if (!accountIds.length) return workload;
  const jql = `project = ${PROJECT} AND statusCategory != Done AND assignee in (${accountIds.join(", ")})`;
  const { issues } = await jira.search(jql);
  for (const issue of issues) {
    if (issue.key === excludeKey) continue;
    const w = workload[issue.fields.assignee?.accountId];
    if (!w) continue;
    const prio = issue.fields.priority.name;
    w.open_issues += 1;
    w.priority_points += PRIORITY_POINTS[prio] ?? 3;
    if (prio === "High" || prio === "Highest") w.high_priority_open += 1;
    if (issue.fields.duedate && daysUntil(issue.fields.duedate) <= DUE_SOON_DAYS) w.due_soon_open += 1;
  }
  return workload;
}

// Decision table 5.1.1, mirrored on the client so the manager gets the message before a round trip.
export function validateRequirements(priority, requirements, catalogIds) {
  if (!priority) return "Norādiet uzdevuma prioritāti";
  if (!requirements.some((r) => r.required)) return "Norādiet vismaz vienu obligāto kvalifikāciju";
  if (requirements.some((r) => !catalogIds.has(r.skill_id))) return "Nezināma kvalifikācija, atjaunojiet katalogu";
  return null;
}

async function loadTeam(excludeKey) {
  let users;
  try {
    users = await jira.assignableUsers(PROJECT);
  } catch (err) {
    throw new FlowError("Neizdevās iegūt datus no Jira");
  }
  const [employees, workload] = await Promise.all([
    data.employees(),
    fetchWorkload(users.map((u) => u.accountId), excludeKey),
  ]);
  const byAcc = Object.fromEntries(employees.map((e) => [e.jira_account_id, e]));
  const candidates = users.map((u) => {
    const emp = byAcc[u.accountId];
    return {
      account_id: u.accountId,
      name: u.displayName,
      available: emp ? emp.status === "active" : true,
      skills: Object.fromEntries((emp?.skills ?? []).map((s) => [s.name, s.level])),
      workload: workload[u.accountId],
      has_profile: Boolean(emp),
    };
  });
  data.saveSnapshots(users.map((u) => ({ jira_account_id: u.accountId, ...workload[u.accountId] }))).catch(() => {});
  return { users, candidates, takenAt: new Date() };
}

async function callAlgorithm(tasks, candidates, settings, weights) {
  const body = {
    tasks,
    candidates: candidates.map(({ has_profile, ...c }) => c),
    weights,
    workload_limit: settings.workload_limit,
    top_n: settings.top_n,
    max_new_per_candidate: settings.max_new_per_candidate,
  };
  return algorithm.recommend(body, settings.timeout_ms);
}

function toTask(issue, requirements) {
  return {
    key: issue.key,
    priority: issue.fields.priority.name,
    requirements: requirements.map((r) => ({ skill: r.skill, required: r.required, min_level: r.min_level })),
  };
}

// Single task: "Meklēt kandidātus".
export async function findCandidates(issueKey, onStep = () => {}) {
  const [settings, weights] = await Promise.all([forge.get("settings.project"), forge.get("weights.config")]);
  if (!settings.enabled) throw new FlowError("Uzdevumu sadale šajā projektā ir izslēgta (Iestatījumi)", "warning");

  const issue = await jira.issue(issueKey);
  const { requirements } = await data.requirements(issueKey);
  if (!requirements.some((r) => r.required)) {
    throw new FlowError("Norādiet vismaz vienu obligāto kvalifikāciju", "warning");
  }
  onStep("validated");
  const team = await loadTeam(issueKey);
  onStep("jira");

  try {
    const res = await callAlgorithm([toTask(issue, requirements)], team.candidates, settings, weights);
    onStep("scored");
    return { mode: "scored", issue, settings, weights, team, result: res.results[0] };
  } catch (err) {
    // Decision table 5.1.4, rule 1: keep manual assignment possible when the service is down.
    if (err instanceof ApiError && (err.status === 0 || err.status >= 500)) {
      return { mode: "manual", issue, settings, team, error: "Aprēķinu serviss nav pieejams" };
    }
    throw err;
  }
}

// Batch mode: every unassigned task with requirements, solved together by the Hungarian algorithm.
export async function planBatch() {
  const [settings, weights, allReqs] = await Promise.all([
    forge.get("settings.project"), forge.get("weights.config"), data.allRequirements(),
  ]);
  if (!settings.enabled) throw new FlowError("Uzdevumu sadale šajā projektā ir izslēgta (Iestatījumi)", "warning");
  const { issues } = await jira.search(`project = ${PROJECT} AND statusCategory != Done AND assignee is EMPTY`);
  const ready = issues.filter((i) => (allReqs[i.key] ?? []).some((r) => r.required));
  const skipped = issues.filter((i) => !ready.includes(i));
  if (!ready.length) throw new FlowError("Nav neviena nepiešķirta uzdevuma ar norādītām prasībām", "warning");

  const team = await loadTeam(null);
  try {
    const res = await callAlgorithm(ready.map((i) => toTask(i, allReqs[i.key])), team.candidates, settings, weights);
    return { issues: ready, skipped, team, res, settings };
  } catch (err) {
    if (err instanceof ApiError && (err.status === 0 || err.status >= 500)) {
      throw new FlowError("Aprēķinu serviss nav pieejams — uzdevumus var piešķirt manuāli katra uzdevuma skatā");
    }
    throw err;
  }
}

// Decision table 5.1.5: assign in Jira first, log the decision only after Jira confirms.
export async function assign({ issueKey, chosen, recommended, scores, reason = "", mode = "single" }) {
  try {
    await jira.assign(issueKey, chosen.account_id);
  } catch (err) {
    await data.writeAudit({ action: "decision.failed", entity: `issue:${issueKey}`, details: err.message })
      .catch(() => {});
    throw new FlowError(`Piešķiršana Jira neizdevās (${err.message}). Uzdevums atstāts bez izpildītāja.`);
  }
  return data.saveDecision({
    issue_key: issueKey,
    recommended_account_id: recommended?.account_id ?? null,
    chosen_account_id: chosen.account_id,
    chosen_name: chosen.name,
    recommended_score: recommended?.score ?? null,
    chosen_score: chosen.score ?? null,
    scores,
    reason,
    mode,
    manager: MANAGER,
  });
}
