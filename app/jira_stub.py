"""Local stand-in for the Jira Cloud REST API v3.

The prototype runs without a real Jira site, so this router serves the handful of endpoints
the Jira integration sub-module calls, with the same paths and payload shapes. Data persists
in a JSON file. Pointing the front end at a real Jira site would not change the plugin code.
"""
import json
import re
import threading
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

router = APIRouter(prefix="/jira/rest/api/3", tags=["jira-stub"])

DONE_STATUSES = {"Pabeigts"}


class JiraStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _store(request: Request) -> JiraStore:
    return request.app.state.jira


def _user_ref(data: dict, account_id: str | None) -> dict | None:
    if not account_id:
        return None
    for u in data["users"]:
        if u["accountId"] == account_id:
            return {"accountId": u["accountId"], "displayName": u["displayName"]}
    return None


def _render(data: dict, issue: dict) -> dict:
    status = issue["status"]
    return {
        "id": str(issue["id"]),
        "key": issue["key"],
        "fields": {
            "summary": issue["summary"],
            "description": issue.get("description", ""),
            "issuetype": {"name": issue.get("issuetype", "Uzdevums")},
            "project": {"key": issue["project"]},
            "priority": {"name": issue["priority"]},
            "status": {
                "name": status,
                "statusCategory": {"key": "done" if status in DONE_STATUSES else
                                   "new" if status == "Jādara" else "indeterminate"},
            },
            "assignee": _user_ref(data, issue.get("assignee")),
            "duedate": issue.get("duedate"),
            "created": issue.get("created"),
        },
    }


def _find(data: dict, key: str) -> dict:
    for issue in data["issues"]:
        if issue["key"] == key:
            return issue
    raise HTTPException(404, {"errorMessages": [f"Uzdevums {key} neeksistē"]})


@router.get("/project/{project_key}")
def get_project(project_key: str, request: Request):
    data = _store(request).load()
    for p in data["projects"]:
        if p["key"] == project_key:
            return p
    raise HTTPException(404, {"errorMessages": ["Projekts neeksistē"]})


@router.get("/user/assignable/search")
def assignable_users(project: str, request: Request):
    data = _store(request).load()
    return [u for u in data["users"] if u.get("active", True) and project in u.get("projects", [])]


@router.get("/issue/{key}")
def get_issue(key: str, request: Request):
    data = _store(request).load()
    return _render(data, _find(data, key))


class IssueCreate(BaseModel):
    fields: dict


@router.post("/issue", status_code=201)
def create_issue(body: IssueCreate, request: Request):
    store = _store(request)
    f = body.fields
    summary = (f.get("summary") or "").strip()
    if not summary:
        raise HTTPException(400, {"errors": {"summary": "Nosaukums ir obligāts"}})
    with store.lock:
        data = store.load()
        project = f.get("project", {}).get("key", "DEV")
        data["next_id"] += 1
        issue = {
            "id": 10000 + data["next_id"],
            "key": f"{project}-{data['next_id']}",
            "project": project,
            "summary": summary,
            "description": f.get("description", ""),
            "issuetype": f.get("issuetype", {}).get("name", "Uzdevums"),
            "priority": f.get("priority", {}).get("name", "Medium"),
            "status": "Jādara",
            "assignee": None,
            "duedate": f.get("duedate"),
            "created": date.today().isoformat(),
        }
        data["issues"].append(issue)
        store.save(data)
    return {"id": str(issue["id"]), "key": issue["key"]}


@router.put("/issue/{key}", status_code=204)
def update_issue(key: str, body: IssueCreate, request: Request):
    store = _store(request)
    with store.lock:
        data = store.load()
        issue = _find(data, key)
        f = body.fields
        if "priority" in f:
            issue["priority"] = f["priority"]["name"]
        for field in ("summary", "description", "duedate"):
            if field in f:
                issue[field] = f[field]
        if "status" in f:
            issue["status"] = f["status"]["name"]
        store.save(data)
    return Response(status_code=204)


class AssigneeBody(BaseModel):
    accountId: str | None


@router.put("/issue/{key}/assignee", status_code=204)
def set_assignee(key: str, body: AssigneeBody, request: Request):
    store = _store(request)
    with store.lock:
        data = store.load()
        issue = _find(data, key)
        if body.accountId and not _user_ref(data, body.accountId):
            raise HTTPException(400, {"errorMessages": ["Lietotājs nav atrasts vai nav piešķirams"]})
        issue["assignee"] = body.accountId
        if body.accountId and issue["status"] == "Jādara":
            issue["status"] = "Procesā"
        store.save(data)
    return Response(status_code=204)


class SearchBody(BaseModel):
    jql: str = ""
    maxResults: int = 100


_CLAUSE = re.compile(r"\s+AND\s+", re.IGNORECASE)


def _matches(issue: dict, clauses: list[str]) -> bool:
    """Supports the JQL subset the plugin uses: project, assignee in/is EMPTY, statusCategory."""
    for raw in clauses:
        c = raw.strip()
        if not c:
            continue
        m = re.fullmatch(r"project\s*=\s*\"?(\w+)\"?", c, re.I)
        if m:
            if issue["project"] != m.group(1):
                return False
            continue
        m = re.fullmatch(r"assignee\s+in\s*\((.*)\)", c, re.I)
        if m:
            ids = [s.strip().strip("\"'") for s in m.group(1).split(",") if s.strip()]
            if issue.get("assignee") not in ids:
                return False
            continue
        if re.fullmatch(r"assignee\s+is\s+EMPTY", c, re.I):
            if issue.get("assignee"):
                return False
            continue
        if re.fullmatch(r"assignee\s+is\s+not\s+EMPTY", c, re.I):
            if not issue.get("assignee"):
                return False
            continue
        m = re.fullmatch(r"statusCategory\s*(!=|=)\s*\"?(\w+)\"?", c, re.I)
        if m:
            is_done = issue["status"] in DONE_STATUSES
            want_done = m.group(2).casefold() == "done"
            if (m.group(1) == "=") != (is_done == want_done):
                return False
            continue
        raise HTTPException(400, {"errorMessages": [f"Neatbalstīts JQL: {c}"]})
    return True


@router.post("/search/jql")
def search(body: SearchBody, request: Request):
    data = _store(request).load()
    jql = re.split(r"\s+ORDER\s+BY\s+", body.jql, flags=re.I)[0]
    clauses = _CLAUSE.split(jql) if jql.strip() else []
    issues = [_render(data, i) for i in data["issues"] if _matches(i, clauses)]
    return {"issues": issues[: body.maxResults], "total": len(issues)}
