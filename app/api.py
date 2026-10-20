"""Server side of the system: algorithm endpoint and the PostgreSQL data access API (ADR-001)."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .algorithm import RecommendRequest, RecommendResponse, recommend
from .algorithm.contract import PRIORITY_WEIGHT
from .models import (AssignmentDecision, AuditLog, Employee, EmployeeSkill, Skill, TaskRequirement,
                     WorkloadSnapshot)

router = APIRouter(prefix="/api/v1")
forge_router = APIRouter(prefix="/forge/storage", tags=["forge-storage"])

DEFAULT_MANAGER = "Vadītājs (demo)"
EMPLOYEE_STATUSES = {"active", "on_leave", "inactive"}
FORGE_KEYS = {"weights.config", "settings.project"}


def get_db(request: Request):
    db = request.app.state.SessionLocal()
    try:
        yield db
    finally:
        db.close()


DB = Annotated[Session, Depends(get_db)]


def iso(dt: datetime) -> str:
    # SQLite drops the offset; values are always written in UTC.
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def fail(status: int, code: str, message: str):
    raise HTTPException(status, {"code": code, "message": message})


def audit(db: Session, action: str, entity: str, details: str = "", actor: str = DEFAULT_MANAGER):
    db.add(AuditLog(actor=actor, action=action, entity=entity, details=details))


def refresh_catalog_cache(request: Request, db: Session) -> None:
    """PostgreSQL is the source of truth; Forge Storage keeps a versioned copy (risk table 10)."""
    forge = request.app.state.forge
    version = forge.get("skills.catalog").get("version", 0) + 1
    items = [{"id": s.id, "name": s.name, "category": s.category}
             for s in db.scalars(select(Skill).order_by(Skill.category, Skill.name))]
    forge.set("skills.catalog", {"version": version, "items": items})


# ---------------------------------------------------------------- health / algorithm

@router.get("/health")
def health(request: Request, db: DB):
    db.execute(select(1))
    outage = request.app.state.forge.get("settings.project").get("demo_algorithm_outage", False)
    return {"status": "degraded" if outage else "ok", "database": "ok",
            "algorithm": "unavailable" if outage else "ok", "api_version": "1"}


@router.post("/algorithm/recommend", response_model=RecommendResponse)
def algorithm_recommend(body: RecommendRequest, request: Request):
    if request.app.state.forge.get("settings.project").get("demo_algorithm_outage", False):
        fail(503, "service_unavailable", "Aprēķinu serviss nav pieejams")
    return recommend(body)


# ---------------------------------------------------------------- skill catalog

class SkillBody(BaseModel):
    name: str | None = None
    category: str = ""
    description: str = ""


def skill_out(s: Skill) -> dict:
    return {"id": s.id, "name": s.name, "category": s.category, "description": s.description}


@router.get("/skills")
def list_skills(db: DB):
    usage = dict(db.execute(select(EmployeeSkill.skill_id, func.count()).group_by(EmployeeSkill.skill_id)).all())
    return [skill_out(s) | {"employees": usage.get(s.id, 0)}
            for s in db.scalars(select(Skill).order_by(Skill.category, Skill.name))]


@router.post("/skills", status_code=201)
def create_skill(body: SkillBody, request: Request, db: DB):
    name = (body.name or "").strip()
    if not name:
        fail(422, "missing_data", "Ievadiet kvalifikācijas nosaukumu")
    skill = Skill(name=name, category=body.category.strip(), description=body.description.strip())
    db.add(skill)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        fail(409, "duplicate", "Šāda kvalifikācija katalogā jau ir")
    audit(db, "skill.create", f"skill:{skill.id}", name)
    db.commit()
    refresh_catalog_cache(request, db)
    return skill_out(skill)


@router.put("/skills/{skill_id}")
def update_skill(skill_id: int, body: SkillBody, request: Request, db: DB):
    skill = db.get(Skill, skill_id) or fail(404, "not_found", "Kvalifikācija nav atrasta")
    name = (body.name or "").strip()
    if not name:
        fail(422, "missing_data", "Ievadiet kvalifikācijas nosaukumu")
    skill.name, skill.category, skill.description = name, body.category.strip(), body.description.strip()
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        fail(409, "duplicate", "Šāda kvalifikācija katalogā jau ir")
    audit(db, "skill.update", f"skill:{skill.id}", name)
    db.commit()
    refresh_catalog_cache(request, db)
    return skill_out(skill)


@router.delete("/skills/{skill_id}", status_code=204)
def delete_skill(skill_id: int, request: Request, db: DB):
    skill = db.get(Skill, skill_id) or fail(404, "not_found", "Kvalifikācija nav atrasta")
    used_by = db.scalar(select(func.count()).select_from(EmployeeSkill).where(EmployeeSkill.skill_id == skill_id))
    used_in = db.scalar(select(func.count()).select_from(TaskRequirement).where(TaskRequirement.skill_id == skill_id))
    if used_by or used_in:
        fail(409, "in_use", f"Kvalifikācija tiek izmantota ({used_by} darbiniekiem, {used_in} uzdevumu prasībās)")
    audit(db, "skill.delete", f"skill:{skill.id}", skill.name)
    db.delete(skill)
    db.commit()
    refresh_catalog_cache(request, db)
    return Response(status_code=204)


# ---------------------------------------------------------------- employees and their skills

def employee_out(e: Employee) -> dict:
    return {
        "id": e.id, "jira_account_id": e.jira_account_id, "display_name": e.display_name,
        "team": e.team, "status": e.status,
        "skills": sorted(({"skill_id": es.skill_id, "name": es.skill.name, "level": es.level} for es in e.skills),
                         key=lambda s: (-s["level"], s["name"])),
    }


def _employees(db: Session):
    return db.scalars(select(Employee).options(selectinload(Employee.skills).selectinload(EmployeeSkill.skill))
                      .order_by(Employee.display_name))


@router.get("/employees")
def list_employees(db: DB):
    return [employee_out(e) for e in _employees(db)]


class JiraUser(BaseModel):
    accountId: str
    displayName: str


class ImportBody(BaseModel):
    users: list[JiraUser]


@router.post("/employees/import-from-jira")
def import_from_jira(body: ImportBody, db: DB):
    known = set(db.scalars(select(Employee.jira_account_id)))
    added = []
    for u in body.users:
        if u.accountId not in known:
            db.add(Employee(jira_account_id=u.accountId, display_name=u.displayName))
            added.append(u.displayName)
    if added:
        audit(db, "employee.import", "employees", ", ".join(added))
    db.commit()
    return {"added": added}


class EmployeePatch(BaseModel):
    status: str | None = None
    team: str | None = None


@router.patch("/employees/{employee_id}")
def patch_employee(employee_id: int, body: EmployeePatch, db: DB):
    emp = db.get(Employee, employee_id) or fail(404, "not_found", "Darbinieks nav atrasts")
    if body.status is not None:
        if body.status not in EMPLOYEE_STATUSES:
            fail(422, "invalid_status", "Nederīgs statuss")
        audit(db, "employee.status", f"employee:{emp.id}", f"{emp.display_name}: {emp.status} → {body.status}")
        emp.status = body.status
    if body.team is not None:
        emp.team = body.team.strip()
    db.commit()
    return employee_out(emp)


class EmployeeSkillBody(BaseModel):
    skill_id: int | None = None
    level: int | None = None


@router.post("/employees/{employee_id}/skills", status_code=201)
def add_employee_skill(employee_id: int, body: EmployeeSkillBody, db: DB):
    """Decision table 5.1.2."""
    emp = db.get(Employee, employee_id)
    if emp is None or body.skill_id is None or body.level is None:
        fail(422, "missing_data", "Ievadiet visus nepieciešamos datus")
    if not 1 <= body.level <= 5:
        fail(422, "invalid_level", "Līmenim jābūt no 1 līdz 5")
    skill = db.get(Skill, body.skill_id) or fail(422, "unknown_skill", "Nezināma kvalifikācija, atjaunojiet katalogu")
    exists = db.scalar(select(EmployeeSkill).where(EmployeeSkill.employee_id == employee_id,
                                                   EmployeeSkill.skill_id == body.skill_id))
    if exists:
        fail(409, "duplicate", "Darbiniekam šāda kvalifikācija jau ir")
    db.add(EmployeeSkill(employee_id=employee_id, skill_id=body.skill_id, level=body.level))
    audit(db, "employee.skill.add", f"employee:{emp.id}", f"{emp.display_name}: {skill.name} = {body.level}")
    db.commit()
    db.refresh(emp)
    return employee_out(emp)


@router.put("/employees/{employee_id}/skills/{skill_id}")
def update_employee_skill(employee_id: int, skill_id: int, body: EmployeeSkillBody, db: DB):
    es = db.scalar(select(EmployeeSkill).where(EmployeeSkill.employee_id == employee_id,
                                               EmployeeSkill.skill_id == skill_id))
    if es is None:
        fail(404, "not_found", "Darbiniekam šādas kvalifikācijas nav")
    if body.level is None or not 1 <= body.level <= 5:
        fail(422, "invalid_level", "Līmenim jābūt no 1 līdz 5")
    audit(db, "employee.skill.level", f"employee:{employee_id}",
          f"{es.employee.display_name}: {es.skill.name} {es.level} → {body.level}")
    es.level = body.level
    db.commit()
    return employee_out(db.get(Employee, employee_id))


@router.delete("/employees/{employee_id}/skills/{skill_id}")
def remove_employee_skill(employee_id: int, skill_id: int, db: DB):
    es = db.scalar(select(EmployeeSkill).where(EmployeeSkill.employee_id == employee_id,
                                               EmployeeSkill.skill_id == skill_id))
    if es is None:
        fail(404, "not_found", "Darbiniekam šādas kvalifikācijas nav")
    emp = es.employee
    audit(db, "employee.skill.remove", f"employee:{employee_id}", f"{emp.display_name}: {es.skill.name}")
    db.delete(es)
    db.commit()
    db.refresh(emp)
    return employee_out(emp)


# ---------------------------------------------------------------- task requirements

class RequirementIn(BaseModel):
    skill_id: int
    required: bool = True
    min_level: int = 1


class RequirementsBody(BaseModel):
    priority: str | None = None
    requirements: list[RequirementIn] = []


def requirements_out(db: Session, key: str) -> list[dict]:
    rows = db.scalars(select(TaskRequirement).options(selectinload(TaskRequirement.skill))
                      .where(TaskRequirement.issue_key == key).order_by(TaskRequirement.id))
    return [{"skill_id": r.skill_id, "skill": r.skill.name, "required": r.required, "min_level": r.min_level}
            for r in rows]


@router.get("/tasks/requirements")
def all_requirements(db: DB):
    keys = db.scalars(select(TaskRequirement.issue_key).distinct())
    return {k: requirements_out(db, k) for k in keys}


@router.get("/tasks/{issue_key}/requirements")
def get_requirements(issue_key: str, db: DB):
    return {"issue_key": issue_key, "requirements": requirements_out(db, issue_key)}


@router.put("/tasks/{issue_key}/requirements")
def save_requirements(issue_key: str, body: RequirementsBody, db: DB):
    """Decision table 5.1.1: priority, at least one mandatory skill, every skill in the catalog."""
    if not body.priority or body.priority not in PRIORITY_WEIGHT:
        fail(422, "missing_priority", "Norādiet uzdevuma prioritāti")
    if not any(r.required for r in body.requirements):
        fail(422, "missing_required_skill", "Norādiet vismaz vienu obligāto kvalifikāciju")
    known = set(db.scalars(select(Skill.id)))
    if any(r.skill_id not in known for r in body.requirements):
        fail(422, "unknown_skill", "Nezināma kvalifikācija, atjaunojiet katalogu")
    if len({r.skill_id for r in body.requirements}) != len(body.requirements):
        fail(422, "duplicate_skill", "Katru kvalifikāciju var norādīt tikai vienu reizi")
    if any(not 1 <= r.min_level <= 5 for r in body.requirements):
        fail(422, "invalid_level", "Līmenim jābūt no 1 līdz 5")

    for old in db.scalars(select(TaskRequirement).where(TaskRequirement.issue_key == issue_key)):
        db.delete(old)
    db.flush()
    for r in body.requirements:
        db.add(TaskRequirement(issue_key=issue_key, skill_id=r.skill_id, required=r.required,
                               min_level=r.min_level))
    audit(db, "task.requirements", f"issue:{issue_key}", f"{len(body.requirements)} prasības, {body.priority}")
    db.commit()
    return {"issue_key": issue_key, "priority": body.priority, "requirements": requirements_out(db, issue_key)}


# ---------------------------------------------------------------- workload snapshots

class SnapshotIn(BaseModel):
    jira_account_id: str
    open_issues: int = 0
    priority_points: int = 0
    high_priority_open: int = 0
    due_soon_open: int = 0


@router.post("/workload-snapshots", status_code=201)
def save_snapshots(body: list[SnapshotIn], db: DB):
    # Snapshots are derived from Jira and may be overwritten freely (section 3.3).
    for s in body:
        db.add(WorkloadSnapshot(**s.model_dump()))
    db.commit()
    return {"saved": len(body)}


# ---------------------------------------------------------------- decision history and audit

class DecisionIn(BaseModel):
    issue_key: str
    recommended_account_id: str | None = None
    chosen_account_id: str
    chosen_name: str = ""
    recommended_score: float | None = None
    chosen_score: float | None = None
    scores: dict = {}
    reason: str = ""
    mode: str = "single"
    manager: str = DEFAULT_MANAGER


def decision_out(d: AssignmentDecision) -> dict:
    return {
        "id": d.id, "issue_key": d.issue_key, "created_at": iso(d.created_at), "manager": d.manager,
        "mode": d.mode,
        "recommended": d.recommended.display_name if d.recommended else None,
        "recommended_account_id": d.recommended_account_id,
        "chosen": d.chosen.display_name if d.chosen else d.chosen_name,
        "chosen_account_id": d.chosen_account_id,
        "followed_recommendation": d.followed_recommendation,
        "recommended_score": d.recommended_score, "chosen_score": d.chosen_score,
        "reason": d.reason, "scores": d.scores,
    }


@router.post("/decisions", status_code=201)
def save_decision(body: DecisionIn, db: DB):
    by_acc = {e.jira_account_id: e for e in db.scalars(select(Employee))}
    rec, chosen = by_acc.get(body.recommended_account_id or ""), by_acc.get(body.chosen_account_id)
    followed = body.recommended_account_id is not None and body.recommended_account_id == body.chosen_account_id
    if not followed and body.recommended_account_id and not body.reason.strip():
        fail(422, "missing_reason", "Norādiet, kāpēc izvēlēts cits darbinieks")
    d = AssignmentDecision(
        issue_key=body.issue_key,
        recommended_employee_id=rec.id if rec else None,
        recommended_account_id=body.recommended_account_id,
        chosen_employee_id=chosen.id if chosen else None,
        chosen_account_id=body.chosen_account_id,
        chosen_name=chosen.display_name if chosen else body.chosen_name,
        followed_recommendation=followed,
        recommended_score=body.recommended_score, chosen_score=body.chosen_score,
        scores=body.scores, reason=body.reason.strip(), mode=body.mode, manager=body.manager,
    )
    db.add(d)
    audit(db, "decision.assign", f"issue:{body.issue_key}",
          f"→ {d.chosen_name}" + ("" if followed else " (ne ieteiktais)"), actor=body.manager)
    db.commit()
    db.refresh(d)
    return decision_out(d)


@router.get("/decisions")
def list_decisions(db: DB, issue_key: str | None = None):
    q = select(AssignmentDecision).order_by(AssignmentDecision.created_at.desc(), AssignmentDecision.id.desc())
    if issue_key:
        q = q.where(AssignmentDecision.issue_key == issue_key)
    return [decision_out(d) for d in db.scalars(q)]


class AuditIn(BaseModel):
    action: str
    entity: str
    details: str = ""


@router.post("/audit-log", status_code=201)
def write_audit(body: AuditIn, db: DB):
    audit(db, body.action, body.entity, body.details)
    db.commit()
    return {"ok": True}


@router.get("/audit-log")
def read_audit(db: DB, limit: int = 100):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit))
    return [{"id": a.id, "actor": a.actor, "action": a.action, "entity": a.entity, "details": a.details,
             "created_at": iso(a.created_at)} for a in rows]


@router.post("/dev/reset")
def dev_reset(request: Request):
    from .main import reset_demo_data
    s = request.app.state
    s.engine.dispose()
    reset_demo_data(s.database_url, s.data_dir, app=request.app)
    return {"ok": True}


# ---------------------------------------------------------------- Forge Storage emulation

@forge_router.get("/{key}")
def forge_get(key: str, request: Request):
    return request.app.state.forge.get(key)


@forge_router.put("/{key}")
def forge_put(key: str, value: dict, request: Request, db: DB):
    if key not in FORGE_KEYS:
        fail(400, "readonly_key", "Šo atslēgu var mainīt tikai sistēma")
    if key == "weights.config":
        for k in ("skills", "workload", "priority", "deadline"):
            v = value.get(k)
            if not isinstance(v, (int, float)) or v < 0:
                fail(422, "invalid_weight", "Svariem jābūt nenegatīviem skaitļiem")
        if sum(value[k] for k in ("skills", "workload", "priority", "deadline")) == 0:
            fail(422, "invalid_weight", "Vismaz vienam svaram jābūt lielākam par 0")
    if key == "settings.project":
        value = request.app.state.forge.get(key) | value
        if not 1 <= int(value.get("top_n", 5)) <= 50:
            fail(422, "invalid_setting", "Kandidātu skaitam jābūt no 1 līdz 50")
    audit(db, "config.update", key, ", ".join(f"{k}={v}" for k, v in value.items()))
    db.commit()
    return request.app.state.forge.set(key, value)
