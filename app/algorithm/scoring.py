"""Weighted fit score with an explanation of which factors mattered (architecture 2.1.2, table 4)."""
from .contract import CandidateIn, FactorScores, ScoredCandidate, TaskIn, Weights
from .filtering import norm, skill_levels

MAX_LEVEL = 5
DESIRABLE_WEIGHT = 0.5
OVERLOAD_PENALTY = 0.20
CONCURRENT_HIGH_CAP = 3
DUE_SOON_CAP = 3

FACTOR_LABELS = {
    "skills": "kvalifikāciju atbilstība",
    "workload": "pašreizējā noslodze",
    "priority": "citi augstas prioritātes darbi",
    "deadline": "tuvojošies termiņi",
}


def _skill_factor(task: TaskIn, levels: dict[str, int]) -> tuple[float, list[str], list[str]]:
    total_w = 0.0
    acc = 0.0
    matched, missing_desirable = [], []
    for req in task.requirements:
        w = 1.0 if req.required else DESIRABLE_WEIGHT
        have = levels.get(norm(req.skill), 0)
        total_w += w
        acc += w * min(have, MAX_LEVEL) / MAX_LEVEL
        if have:
            matched.append(f"{req.skill} {have}/{MAX_LEVEL}")
        elif not req.required:
            missing_desirable.append(req.skill)
    return (acc / total_w if total_w else 1.0), matched, missing_desirable


def _normalised_weights(weights: Weights) -> dict[str, float]:
    raw = weights.model_dump()
    total = sum(raw.values())
    if total == 0:
        return {k: 1 / len(raw) for k in raw}
    return {k: v / total for k, v in raw.items()}


def score_candidate(task: TaskIn, cand: CandidateIn, weights: Weights, workload_limit: int) -> ScoredCandidate:
    levels = skill_levels(cand)
    skill_f, matched, missing_desirable = _skill_factor(task, levels)
    wl = cand.workload

    factors = {
        "skills": skill_f,
        "workload": 1 - min(wl.priority_points / workload_limit, 1.0),
        "priority": 1 - min(wl.high_priority_open / CONCURRENT_HIGH_CAP, 1.0),
        "deadline": 1 - min(wl.due_soon_open / DUE_SOON_CAP, 1.0),
    }
    w = _normalised_weights(weights)
    contributions = {k: w[k] * factors[k] for k in factors}
    base = sum(contributions.values())

    overloaded = wl.priority_points > workload_limit
    penalty = OVERLOAD_PENALTY if overloaded else 0.0
    score = max(base - penalty, 0.0)

    explanation = []
    strongest = max(contributions, key=contributions.get)
    explanation.append(f"Visvairāk ietekmēja: {FACTOR_LABELS[strongest]} (+{contributions[strongest] * 100:.0f})")
    if matched:
        explanation.append("Kvalifikācijas: " + ", ".join(matched))
    explanation.append(
        f"Noslodze: {wl.open_issues} atvērti uzdevumi, {wl.priority_points}/{workload_limit} prioritātes punkti"
    )
    if wl.high_priority_open:
        explanation.append(f"Augstas prioritātes darbi: {wl.high_priority_open}")
    if wl.due_soon_open:
        explanation.append(f"Termiņš 7 dienu laikā: {wl.due_soon_open}")
    if missing_desirable:
        explanation.append("Trūkst vēlamās: " + ", ".join(missing_desirable))
    if overloaded:
        explanation.append(f"Pārsniegta noslodzes robeža (−{OVERLOAD_PENALTY * 100:.0f})")

    return ScoredCandidate(
        account_id=cand.account_id,
        name=cand.name,
        score=round(score * 100, 1),
        factors=FactorScores(**{k: round(v, 3) for k, v in factors.items()}),
        contributions=FactorScores(**{k: round(v * 100, 1) for k, v in contributions.items()}),
        penalty=round(penalty * 100, 1),
        explanation=explanation,
    )
