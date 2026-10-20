"""Algorithm module tested in isolation: no Jira, no database (architecture 6.3)."""
from app.algorithm import RecommendRequest, recommend
from app.algorithm.contract import CandidateIn, Requirement, TaskIn, Weights, Workload
from app.algorithm.filtering import filter_candidates
from app.algorithm.optimization import optimal_assignment
from app.algorithm.scoring import OVERLOAD_PENALTY, score_candidate


def cand(acc, skills, points=0, available=True, high=0, due=0, open_issues=None):
    return CandidateIn(
        account_id=acc, name=acc.upper(), available=available, skills=skills,
        workload=Workload(open_issues=open_issues if open_issues is not None else points // 3,
                          priority_points=points, high_priority_open=high, due_soon_open=due),
    )


def task(key="T-1", priority="Medium", reqs=(("Python", True, 3),)):
    return TaskIn(key=key, priority=priority,
                  requirements=[Requirement(skill=s, required=r, min_level=m) for s, r, m in reqs])


# ---- filtering (decision table 5.1.3)

def test_missing_mandatory_skill_excludes_candidate():
    eligible, excluded = filter_candidates(task(), [cand("a", {"Python": 4}), cand("b", {"SQL": 5})])
    assert [c.account_id for c in eligible] == ["a"]
    assert excluded[0].account_id == "b" and "Python" in excluded[0].reason


def test_level_below_minimum_excludes_candidate():
    _, excluded = filter_candidates(task(reqs=(("Python", True, 4),)), [cand("a", {"Python": 3})])
    assert "vajag ≥4, ir 3" in excluded[0].reason


def test_unavailable_candidate_is_excluded_even_if_qualified():
    eligible, excluded = filter_candidates(task(), [cand("a", {"Python": 5}, available=False)])
    assert eligible == [] and excluded[0].reason == "Nav pieejams"


def test_desirable_skill_does_not_filter():
    t = task(reqs=(("Python", True, 1), ("Docker", False, 3)))
    eligible, _ = filter_candidates(t, [cand("a", {"Python": 2})])
    assert len(eligible) == 1


def test_skill_names_match_case_insensitively():
    eligible, _ = filter_candidates(task(), [cand("a", {"  python ": 3})])
    assert len(eligible) == 1


# ---- scoring

def test_higher_skill_level_scores_higher_with_equal_workload():
    t, w = task(), Weights()
    assert score_candidate(t, cand("a", {"Python": 5}), w, 12).score > \
        score_candidate(t, cand("b", {"Python": 3}), w, 12).score


def test_lower_workload_scores_higher_with_equal_skills():
    t, w = task(), Weights()
    assert score_candidate(t, cand("a", {"Python": 4}, points=2), w, 12).score > \
        score_candidate(t, cand("b", {"Python": 4}, points=9), w, 12).score


def test_overload_penalty_applied_above_limit():
    s = score_candidate(task(), cand("a", {"Python": 5}, points=13), Weights(), 12)
    assert s.penalty == OVERLOAD_PENALTY * 100
    assert any("Pārsniegta noslodzes robeža" in line for line in s.explanation)


def test_no_penalty_exactly_at_limit():
    assert score_candidate(task(), cand("a", {"Python": 5}, points=12), Weights(), 12).penalty == 0


def test_perfect_candidate_scores_100():
    s = score_candidate(task(), cand("a", {"Python": 5}), Weights(), 12)
    assert s.score == 100.0


def test_contributions_add_up_to_score_without_penalty():
    s = score_candidate(task(), cand("a", {"Python": 4}, points=6, high=1, due=1), Weights(), 12)
    total = s.contributions.skills + s.contributions.workload + s.contributions.priority + s.contributions.deadline
    assert abs(total - s.score) < 0.3


def test_weights_change_the_ranking():
    t = task()
    expert_busy = cand("expert", {"Python": 5}, points=10)
    junior_free = cand("junior", {"Python": 3}, points=0)
    skill_heavy = Weights(skills=1, workload=0, priority=0, deadline=0)
    load_heavy = Weights(skills=0.1, workload=1, priority=0, deadline=0)
    r1 = recommend(RecommendRequest(tasks=[t], candidates=[expert_busy, junior_free], weights=skill_heavy))
    r2 = recommend(RecommendRequest(tasks=[t], candidates=[expert_busy, junior_free], weights=load_heavy))
    assert r1.results[0].recommended == "expert"
    assert r2.results[0].recommended == "junior"


def test_all_zero_weights_fall_back_to_equal_weights():
    s = score_candidate(task(), cand("a", {"Python": 5}), Weights(skills=0, workload=0, priority=0, deadline=0), 12)
    assert s.score == 100.0


def test_explanation_names_the_strongest_factor():
    s = score_candidate(task(), cand("a", {"Python": 5}, points=12, high=3, due=3), Weights(), 12)
    assert s.explanation[0].startswith("Visvairāk ietekmēja: kvalifikāciju atbilstība")


# ---- recommend: empty result (5.1.4) and ordering

def test_no_matching_candidates_returns_status_and_empty_list():
    res = recommend(RecommendRequest(tasks=[task(reqs=(("Forge", True, 2),))], candidates=[cand("a", {"Python": 5})]))
    r = res.results[0]
    assert r.status == "no_candidates" and r.candidates == [] and r.recommended is None
    assert len(r.excluded) == 1


def test_no_candidates_at_all():
    res = recommend(RecommendRequest(tasks=[task()], candidates=[]))
    assert res.results[0].status == "no_candidates"


def test_candidates_sorted_and_trimmed_to_top_n():
    cs = [cand(f"c{i}", {"Python": 3 + i % 3}, points=i) for i in range(8)]
    res = recommend(RecommendRequest(tasks=[task()], candidates=cs, top_n=3))
    scores = [c.score for c in res.results[0].candidates]
    assert len(scores) == 3 and scores == sorted(scores, reverse=True)
    assert res.results[0].recommended == res.results[0].candidates[0].account_id


# ---- optimisation (Hungarian algorithm)

def test_hungarian_beats_greedy():
    # Greedy would give T-1 to "a" (its best) and leave T-2 with "b" (40): total 130.
    # The optimum is T-1 -> b, T-2 -> a: total 170.
    t1, t2 = task("T-1"), task("T-2")
    scores = {("T-1", "a"): 90, ("T-1", "b"): 80, ("T-2", "a"): 90, ("T-2", "b"): 40}
    assignment, total = optimal_assignment([t1, t2], ["a", "b"], scores)
    assert assignment == {"T-1": "b", "T-2": "a"} and total == 170


def test_higher_priority_task_wins_a_contested_candidate():
    hi, lo = task("HI", priority="Highest"), task("LO", priority="Low")
    scores = {("HI", "a"): 80, ("LO", "a"): 85}
    assignment, _ = optimal_assignment([hi, lo], ["a"], scores)
    assert assignment == {"HI": "a", "LO": None}


def test_ineligible_pairs_are_never_assigned():
    assignment, _ = optimal_assignment([task("T-1")], ["a", "b"], {("T-1", "b"): 10})
    assert assignment == {"T-1": "b"}


def test_capacity_allows_several_tasks_per_person():
    ts = [task(f"T-{i}") for i in range(3)]
    scores = {(t.key, "a"): 70 for t in ts}
    one, _ = optimal_assignment(ts, ["a"], scores, capacity=1)
    three, _ = optimal_assignment(ts, ["a"], scores, capacity=3)
    assert sum(v is not None for v in one.values()) == 1
    assert all(v == "a" for v in three.values())


def test_batch_recommend_gives_distinct_people():
    ts = [task("T-1", reqs=(("Python", True, 1),)), task("T-2", reqs=(("Python", True, 1),))]
    cs = [cand("a", {"Python": 5}), cand("b", {"Python": 4})]
    res = recommend(RecommendRequest(tasks=ts, candidates=cs))
    assert set(res.assignment.values()) == {"a", "b"}
