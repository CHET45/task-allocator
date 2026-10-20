"""Versioned request/response contract of the algorithm module (API v1).

The algorithm receives every input it needs in the request and never reads Jira or the
database itself (architecture, ADR-001), so it can be tested in isolation.
"""
from typing import Literal

from pydantic import BaseModel, Field

Priority = Literal["Highest", "High", "Medium", "Low", "Lowest"]

PRIORITY_WEIGHT: dict[str, int] = {"Highest": 5, "High": 4, "Medium": 3, "Low": 2, "Lowest": 1}


class Requirement(BaseModel):
    skill: str
    required: bool = True
    min_level: int = Field(1, ge=1, le=5)


class TaskIn(BaseModel):
    key: str
    priority: Priority = "Medium"
    requirements: list[Requirement] = Field(min_length=1)


class Workload(BaseModel):
    open_issues: int = Field(0, ge=0)
    priority_points: int = Field(0, ge=0)
    high_priority_open: int = Field(0, ge=0)
    due_soon_open: int = Field(0, ge=0)


class CandidateIn(BaseModel):
    account_id: str
    name: str
    available: bool = True
    skills: dict[str, int] = Field(default_factory=dict)
    workload: Workload = Field(default_factory=Workload)


class Weights(BaseModel):
    skills: float = Field(0.5, ge=0)
    workload: float = Field(0.25, ge=0)
    priority: float = Field(0.15, ge=0)
    deadline: float = Field(0.10, ge=0)


class RecommendRequest(BaseModel):
    tasks: list[TaskIn] = Field(min_length=1)
    candidates: list[CandidateIn]
    weights: Weights = Field(default_factory=Weights)
    workload_limit: int = Field(12, ge=1, description="Priority points above which a candidate is overloaded")
    top_n: int = Field(5, ge=1, le=50)
    max_new_per_candidate: int = Field(1, ge=1, le=10, description="Batch mode: new tasks one person may get")


class FactorScores(BaseModel):
    skills: float
    workload: float
    priority: float
    deadline: float


class ScoredCandidate(BaseModel):
    account_id: str
    name: str
    score: float = Field(description="0..100 after penalty")
    factors: FactorScores = Field(description="Raw factor values 0..1")
    contributions: FactorScores = Field(description="Points each factor added to the score")
    penalty: float
    explanation: list[str]


class Excluded(BaseModel):
    account_id: str
    name: str
    reason: str


class TaskResult(BaseModel):
    key: str
    status: Literal["ok", "no_candidates"]
    recommended: str | None
    candidates: list[ScoredCandidate]
    excluded: list[Excluded]


class RecommendResponse(BaseModel):
    api_version: Literal["1"] = "1"
    results: list[TaskResult]
    assignment: dict[str, str | None]
    total_score: float
