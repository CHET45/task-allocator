"""Data access API, Jira stub and Forge Storage, checked against the decision tables in section 5."""


def skill_id(client, name):
    return next(s["id"] for s in client.get("/api/v1/skills").json() if s["name"] == name)


def employee(client, account_id):
    return next(e for e in client.get("/api/v1/employees").json() if e["jira_account_id"] == account_id)


def test_health(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"


# ---- skill catalog

def test_skill_crud_and_catalog_cache(client):
    before = client.get("/forge/storage/skills.catalog").json()["version"]
    r = client.post("/api/v1/skills", json={"name": "Kubernetes", "category": "Infrastruktūra"})
    assert r.status_code == 201
    sid = r.json()["id"]
    cache = client.get("/forge/storage/skills.catalog").json()
    assert cache["version"] == before + 1 and any(i["name"] == "Kubernetes" for i in cache["items"])

    assert client.put(f"/api/v1/skills/{sid}", json={"name": "Kubernetes (K8s)"}).status_code == 200
    assert client.delete(f"/api/v1/skills/{sid}").status_code == 204
    assert not any(s["name"].startswith("Kubernetes") for s in client.get("/api/v1/skills").json())


def test_duplicate_skill_name_rejected(client):
    r = client.post("/api/v1/skills", json={"name": "Python"})
    assert r.status_code == 409


def test_skill_in_use_cannot_be_deleted(client):
    r = client.delete(f"/api/v1/skills/{skill_id(client, 'Python')}")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "in_use"


# ---- employee skills (decision table 5.1.2)

def test_assign_skill_rule_1_missing_data(client):
    emp = employee(client, "u02")
    r = client.post(f"/api/v1/employees/{emp['id']}/skills", json={"skill_id": skill_id(client, "Docker")})
    assert r.status_code == 422
    assert r.json()["detail"]["message"] == "Ievadiet visus nepieciešamos datus"


def test_assign_skill_rule_2_already_assigned(client):
    emp = employee(client, "u02")
    r = client.post(f"/api/v1/employees/{emp['id']}/skills", json={"skill_id": skill_id(client, "React"), "level": 2})
    assert r.status_code == 409
    assert r.json()["detail"]["message"] == "Darbiniekam šāda kvalifikācija jau ir"


def test_assign_skill_rule_3_saved(client):
    emp = employee(client, "u02")
    r = client.post(f"/api/v1/employees/{emp['id']}/skills", json={"skill_id": skill_id(client, "Docker"), "level": 3})
    assert r.status_code == 201
    assert {"skill_id": skill_id(client, "Docker"), "name": "Docker", "level": 3} in employee(client, "u02")["skills"]


def test_level_update_and_remove(client):
    emp, sid = employee(client, "u01"), skill_id(client, "Docker")
    client.put(f"/api/v1/employees/{emp['id']}/skills/{sid}", json={"level": 5})
    assert next(s for s in employee(client, "u01")["skills"] if s["skill_id"] == sid)["level"] == 5
    client.delete(f"/api/v1/employees/{emp['id']}/skills/{sid}")
    assert all(s["skill_id"] != sid for s in employee(client, "u01")["skills"])


def test_employee_is_deactivated_not_deleted(client):
    emp = employee(client, "u03")
    assert client.patch(f"/api/v1/employees/{emp['id']}", json={"status": "inactive"}).json()["status"] == "inactive"
    assert employee(client, "u03")["status"] == "inactive"


def test_import_from_jira_adds_only_new_users(client):
    users = client.get("/jira/rest/api/3/user/assignable/search?project=DEV").json()
    r = client.post("/api/v1/employees/import-from-jira", json={"users": users}).json()
    assert r["added"] == ["Paula Grīnberga"]
    assert client.post("/api/v1/employees/import-from-jira", json={"users": users}).json()["added"] == []


# ---- task requirements (decision table 5.1.1)

def put_reqs(client, priority, reqs):
    return client.put("/api/v1/tasks/DEV-26/requirements", json={"priority": priority, "requirements": reqs})


def test_requirements_rule_1_priority_missing(client):
    r = put_reqs(client, None, [{"skill_id": skill_id(client, "Dokumentācija"), "required": True}])
    assert r.json()["detail"]["message"] == "Norādiet uzdevuma prioritāti"


def test_requirements_rule_2_no_mandatory_skill(client):
    r = put_reqs(client, "Low", [{"skill_id": skill_id(client, "Dokumentācija"), "required": False}])
    assert r.json()["detail"]["message"] == "Norādiet vismaz vienu obligāto kvalifikāciju"


def test_requirements_rule_3_unknown_skill(client):
    r = put_reqs(client, "Low", [{"skill_id": 9999, "required": True}])
    assert r.json()["detail"]["message"] == "Nezināma kvalifikācija, atjaunojiet katalogu"


def test_requirements_rule_4_saved(client):
    r = put_reqs(client, "Low", [{"skill_id": skill_id(client, "Dokumentācija"), "required": True, "min_level": 3}])
    assert r.status_code == 200
    saved = client.get("/api/v1/tasks/DEV-26/requirements").json()["requirements"]
    assert saved == [{"skill_id": skill_id(client, "Dokumentācija"), "skill": "Dokumentācija",
                      "required": True, "min_level": 3}]


# ---- Jira stub

def test_jql_open_issues_for_assignees(client):
    r = client.post("/jira/rest/api/3/search/jql",
                    json={"jql": "project = DEV AND statusCategory != Done AND assignee in (u06)"}).json()
    assert r["total"] == 5
    assert all(i["fields"]["assignee"]["accountId"] == "u06" for i in r["issues"])


def test_jql_unassigned(client):
    r = client.post("/jira/rest/api/3/search/jql", json={"jql": "project = DEV AND assignee is EMPTY"}).json()
    assert {i["key"] for i in r["issues"]} == {f"DEV-{n}" for n in range(21, 27)}


def test_create_issue_and_assign(client):
    key = client.post("/jira/rest/api/3/issue", json={"fields": {
        "project": {"key": "DEV"}, "summary": "Jauns", "priority": {"name": "High"}}}).json()["key"]
    assert key == "DEV-27"
    assert client.put(f"/jira/rest/api/3/issue/{key}/assignee", json={"accountId": "u01"}).status_code == 204
    issue = client.get(f"/jira/rest/api/3/issue/{key}").json()
    assert issue["fields"]["assignee"]["accountId"] == "u01" and issue["fields"]["status"]["name"] == "Procesā"


def test_assign_unknown_user_fails(client):
    assert client.put("/jira/rest/api/3/issue/DEV-21/assignee", json={"accountId": "nobody"}).status_code == 400


# ---- algorithm endpoint, decisions, Forge Storage

def test_algorithm_endpoint_contract(client):
    body = {
        "tasks": [{"key": "DEV-21", "priority": "High",
                   "requirements": [{"skill": "Python", "required": True, "min_level": 3}]}],
        "candidates": [{"account_id": "u01", "name": "Anna", "skills": {"Python": 5}},
                       {"account_id": "u02", "name": "Jānis", "skills": {"React": 5}}],
    }
    r = client.post("/api/v1/algorithm/recommend", json=body).json()
    assert r["api_version"] == "1" and r["assignment"] == {"DEV-21": "u01"}
    assert r["results"][0]["excluded"][0]["account_id"] == "u02"


def test_algorithm_rejects_task_without_requirements(client):
    body = {"tasks": [{"key": "X", "requirements": []}], "candidates": []}
    assert client.post("/api/v1/algorithm/recommend", json=body).status_code == 422


def test_simulated_outage_returns_503(client):
    client.put("/forge/storage/settings.project", json={"demo_algorithm_outage": True})
    r = client.post("/api/v1/algorithm/recommend", json={"tasks": [{"key": "X", "requirements": [
        {"skill": "Python"}]}], "candidates": []})
    assert r.status_code == 503
    assert client.get("/api/v1/health").json()["algorithm"] == "unavailable"


def test_decision_saved_with_followed_flag(client):
    d = client.post("/api/v1/decisions", json={"issue_key": "DEV-21", "recommended_account_id": "u01",
                                               "chosen_account_id": "u01", "recommended_score": 88.2,
                                               "chosen_score": 88.2}).json()
    assert d["followed_recommendation"] is True and d["chosen"] == "Anna Bērziņa"
    assert client.get("/api/v1/decisions?issue_key=DEV-21").json()[0]["id"] == d["id"]


def test_override_requires_reason(client):
    body = {"issue_key": "DEV-21", "recommended_account_id": "u01", "chosen_account_id": "u03"}
    assert client.post("/api/v1/decisions", json=body).status_code == 422
    d = client.post("/api/v1/decisions", json=body | {"reason": "Līgai jāapgūst API"}).json()
    assert d["followed_recommendation"] is False and d["recommended"] == "Anna Bērziņa"


def test_weights_validation_and_audit(client):
    assert client.put("/forge/storage/weights.config",
                      json={"skills": -1, "workload": 0, "priority": 0, "deadline": 0}).status_code == 422
    w = {"skills": 0.7, "workload": 0.2, "priority": 0.05, "deadline": 0.05}
    assert client.put("/forge/storage/weights.config", json=w).json() == w
    assert client.get("/forge/storage/weights.config").json() == w
    assert client.get("/api/v1/audit-log").json()[0]["entity"] == "weights.config"


def test_catalog_cache_is_read_only(client):
    assert client.put("/forge/storage/skills.catalog", json={"items": []}).status_code == 400


def test_snapshots_saved(client):
    r = client.post("/api/v1/workload-snapshots", json=[{"jira_account_id": "u01", "open_issues": 2}])
    assert r.json() == {"saved": 1}


def test_reset_restores_demo_data(client):
    client.post("/api/v1/skills", json={"name": "Temp"})
    client.post("/jira/rest/api/3/issue", json={"fields": {"summary": "Temp"}})
    client.post("/api/v1/dev/reset")
    assert not any(s["name"] == "Temp" for s in client.get("/api/v1/skills").json())
    assert client.post("/jira/rest/api/3/search/jql", json={"jql": ""}).json()["total"] == 26
