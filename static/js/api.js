// HTTP clients for the three back ends the plugin talks to: Jira REST API, the data access API
// with the algorithm, and Forge Storage. Each error carries a readable Latvian message.

export class ApiError extends Error {
  constructor(message, status, code) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request(method, url, body, { timeoutMs } = {}) {
  const ctrl = new AbortController();
  const timer = timeoutMs ? setTimeout(() => ctrl.abort(), timeoutMs) : null;
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw new ApiError("Pārsniegts gaidīšanas laiks", 0, "timeout");
    throw new ApiError("Serveris nav sasniedzams", 0, "network");
  } finally {
    if (timer) clearTimeout(timer);
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const d = data?.detail;
    const msg = d?.message
      || d?.errorMessages?.[0]
      || (Array.isArray(d) ? d.map((e) => e.msg).join("; ") : null)
      || (d && Object.values(d.errors || {})[0])
      || `Kļūda ${res.status}`;
    throw new ApiError(msg, res.status, d?.code);
  }
  return data;
}

const JIRA = "/jira/rest/api/3";
export const jira = {
  issue: (key) => request("GET", `${JIRA}/issue/${key}`),
  createIssue: (fields) => request("POST", `${JIRA}/issue`, { fields }),
  updateIssue: (key, fields) => request("PUT", `${JIRA}/issue/${key}`, { fields }),
  assign: (key, accountId) => request("PUT", `${JIRA}/issue/${key}/assignee`, { accountId }),
  assignableUsers: (project) => request("GET", `${JIRA}/user/assignable/search?project=${encodeURIComponent(project)}`),
  search: (jql, maxResults = 200) => request("POST", `${JIRA}/search/jql`, { jql, maxResults }),
};

const V1 = "/api/v1";
export const data = {
  health: () => request("GET", `${V1}/health`, undefined, { timeoutMs: 2000 }),
  skills: () => request("GET", `${V1}/skills`),
  createSkill: (s) => request("POST", `${V1}/skills`, s),
  updateSkill: (id, s) => request("PUT", `${V1}/skills/${id}`, s),
  deleteSkill: (id) => request("DELETE", `${V1}/skills/${id}`),
  employees: () => request("GET", `${V1}/employees`),
  importFromJira: (users) => request("POST", `${V1}/employees/import-from-jira`, { users }),
  patchEmployee: (id, body) => request("PATCH", `${V1}/employees/${id}`, body),
  addEmployeeSkill: (id, skill_id, level) => request("POST", `${V1}/employees/${id}/skills`, { skill_id, level }),
  setEmployeeSkill: (id, skillId, level) => request("PUT", `${V1}/employees/${id}/skills/${skillId}`, { level }),
  removeEmployeeSkill: (id, skillId) => request("DELETE", `${V1}/employees/${id}/skills/${skillId}`),
  requirements: (key) => request("GET", `${V1}/tasks/${key}/requirements`),
  allRequirements: () => request("GET", `${V1}/tasks/requirements`),
  saveRequirements: (key, priority, requirements) =>
    request("PUT", `${V1}/tasks/${key}/requirements`, { priority, requirements }),
  saveSnapshots: (rows) => request("POST", `${V1}/workload-snapshots`, rows),
  saveDecision: (d) => request("POST", `${V1}/decisions`, d),
  decisions: (issueKey) => request("GET", `${V1}/decisions${issueKey ? `?issue_key=${issueKey}` : ""}`),
  audit: () => request("GET", `${V1}/audit-log`),
  writeAudit: (a) => request("POST", `${V1}/audit-log`, a),
  reset: () => request("POST", `${V1}/dev/reset`),
};

export const algorithm = {
  recommend: (body, timeoutMs) => request("POST", `${V1}/algorithm/recommend`, body, { timeoutMs }),
};

export const forge = {
  get: (key) => request("GET", `/forge/storage/${key}`),
  set: (key, value) => request("PUT", `/forge/storage/${key}`, value),
};
