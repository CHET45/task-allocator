"""PostgreSQL tables from the architecture document, section 2.2 (table 5)."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    jira_account_id: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    team: Mapped[str] = mapped_column(String(80), default="")
    # active | on_leave | inactive. Employees are deactivated, never deleted (section 3.3).
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    skills: Mapped[list["EmployeeSkill"]] = relationship(back_populates="employee", cascade="all, delete-orphan")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    category: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(Text, default="")


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"
    __table_args__ = (UniqueConstraint("employee_id", "skill_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    level: Mapped[int] = mapped_column(Integer)

    employee: Mapped[Employee] = relationship(back_populates="skills")
    skill: Mapped[Skill] = relationship()


class TaskRequirement(Base):
    __tablename__ = "task_requirements"
    __table_args__ = (UniqueConstraint("issue_key", "skill_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_key: Mapped[str] = mapped_column(String(32), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    min_level: Mapped[int] = mapped_column(Integer, default=1)

    skill: Mapped[Skill] = relationship()


class WorkloadSnapshot(Base):
    __tablename__ = "workload_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    jira_account_id: Mapped[str] = mapped_column(String(64), index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    open_issues: Mapped[int] = mapped_column(Integer, default=0)
    priority_points: Mapped[int] = mapped_column(Integer, default=0)
    high_priority_open: Mapped[int] = mapped_column(Integer, default=0)
    due_soon_open: Mapped[int] = mapped_column(Integer, default=0)


class AssignmentDecision(Base):
    __tablename__ = "assignment_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_key: Mapped[str] = mapped_column(String(32), index=True)
    recommended_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    chosen_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    # Kept alongside the FKs: a manager may pick a Jira user who has no profile yet.
    recommended_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chosen_account_id: Mapped[str] = mapped_column(String(64))
    chosen_name: Mapped[str] = mapped_column(String(120), default="")
    followed_recommendation: Mapped[bool] = mapped_column(Boolean)
    recommended_score: Mapped[float | None] = mapped_column(nullable=True)
    chosen_score: Mapped[float | None] = mapped_column(nullable=True)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(16), default="single")  # single | batch | manual
    manager: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    recommended: Mapped[Employee | None] = relationship(foreign_keys=[recommended_employee_id])
    chosen: Mapped[Employee | None] = relationship(foreign_keys=[chosen_employee_id])


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(120))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
