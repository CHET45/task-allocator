"""Mandatory requirement check (architecture 5.1.3): drops unavailable or unqualified candidates."""
from .contract import CandidateIn, Excluded, TaskIn


def norm(skill: str) -> str:
    return skill.strip().casefold()


def skill_levels(candidate: CandidateIn) -> dict[str, int]:
    return {norm(name): level for name, level in candidate.skills.items()}


def filter_candidates(task: TaskIn, candidates: list[CandidateIn]) -> tuple[list[CandidateIn], list[Excluded]]:
    eligible: list[CandidateIn] = []
    excluded: list[Excluded] = []

    for cand in candidates:
        if not cand.available:
            excluded.append(Excluded(account_id=cand.account_id, name=cand.name, reason="Nav pieejams"))
            continue

        levels = skill_levels(cand)
        gaps = []
        for req in task.requirements:
            if not req.required:
                continue
            have = levels.get(norm(req.skill), 0)
            if have < req.min_level:
                gaps.append(f"{req.skill} (vajag ≥{req.min_level}, ir {have or 'nav'})")

        if gaps:
            excluded.append(Excluded(
                account_id=cand.account_id,
                name=cand.name,
                reason="Trūkst obligātās kvalifikācijas: " + ", ".join(gaps),
            ))
        else:
            eligible.append(cand)

    return eligible, excluded
