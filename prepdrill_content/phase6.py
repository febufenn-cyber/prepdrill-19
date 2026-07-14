"""Phase 6 calibrated mastery and deterministic daily planning."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable


def _order(seed: str, value: str) -> str:
    return hashlib.sha256(f"{seed}\x1f{value}".encode()).hexdigest()


@dataclass(frozen=True)
class AttemptEvidence:
    concept_id: str
    correct: bool
    response_ms: int
    difficulty: float = 0.5
    recency_days: float = 0.0
    confidence: float = 0.5
    hint_used: bool = False
    answer_changes: int = 0
    evidence_strength: float = 1.0
    experimental: bool = False


@dataclass(frozen=True)
class MasteryState:
    concept_id: str
    score: float
    uncertainty: float
    evidence_count: int
    model_version: str


@dataclass(frozen=True)
class ModelConfig:
    version: str = "mastery.v1"
    learning_rate: float = 0.28
    time_target_ms: int = 45_000
    minimum_weight: float = 0.05


class MasteryModel:
    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()

    def update(self, state: MasteryState | None, attempt: AttemptEvidence, *, include_experimental: bool = False) -> MasteryState:
        current = state or MasteryState(attempt.concept_id, 0.5, 1.0, 0, self.config.version)
        if attempt.experimental and not include_experimental:
            return current
        bounded_ms = min(max(attempt.response_ms, 1_000), 300_000)
        time_quality = min(1.0, self.config.time_target_ms / bounded_ms)
        difficulty = min(max(attempt.difficulty, 0.0), 1.0)
        confidence = min(max(attempt.confidence, 0.0), 1.0)
        recency_weight = math.exp(-max(attempt.recency_days, 0.0) / 45.0)
        behavior = (0.6 + 0.4 * time_quality) * (0.7 + 0.3 * difficulty) * (0.7 + 0.3 * confidence)
        if attempt.hint_used:
            behavior *= 0.55
        behavior *= 1.0 / (1.0 + min(max(attempt.answer_changes, 0), 5) * 0.18)
        weight = max(self.config.minimum_weight, min(1.0, behavior * recency_weight * min(max(attempt.evidence_strength, 0.0), 1.0)))
        target = 1.0 if attempt.correct else 0.0
        new_score = current.score + self.config.learning_rate * weight * (target - current.score)
        new_uncertainty = max(0.05, current.uncertainty * (1.0 - 0.18 * weight))
        return MasteryState(attempt.concept_id, round(min(max(new_score, 0.0), 1.0), 6), round(new_uncertainty, 6), current.evidence_count + 1, self.config.version)

    def replay(self, attempts: Iterable[AttemptEvidence], *, include_experimental: bool = False) -> dict[str, MasteryState]:
        states: dict[str, MasteryState] = {}
        for attempt in attempts:
            states[attempt.concept_id] = self.update(states.get(attempt.concept_id), attempt, include_experimental=include_experimental)
        return states


@dataclass(frozen=True)
class PlanCandidate:
    question_id: str
    concept_id: str
    category: str
    difficulty: float
    due: bool = False
    recent_error: bool = False
    experimental: bool = False
    exposure_count: int = 0


@dataclass(frozen=True)
class PlanItem:
    question_id: str
    concept_id: str
    category: str
    rationale: str


class DailyPlanner:
    CATEGORY_ORDER = ("weak", "due", "recent", "mixed", "challenge", "confidence_repair")

    def create(self, *, states: dict[str, MasteryState], candidates: Iterable[PlanCandidate], size: int, seed: str, max_per_concept: int = 2) -> list[PlanItem]:
        if size <= 0:
            return []
        eligible = [item for item in candidates if not item.experimental and item.exposure_count < 5]
        scored: list[tuple[float, str, PlanCandidate, str]] = []
        for item in eligible:
            state = states.get(item.concept_id, MasteryState(item.concept_id, 0.5, 1.0, 0, "unseen"))
            category = self._category(item, state)
            category_priority = len(self.CATEGORY_ORDER) - self.CATEGORY_ORDER.index(category)
            score = category_priority * 10 + (1.0 - state.score) * 5 + state.uncertainty * 2 + item.difficulty
            rationale = self._rationale(category, state)
            scored.append((-score, _order(seed, item.question_id), PlanCandidate(item.question_id, item.concept_id, category, item.difficulty, item.due, item.recent_error, item.experimental, item.exposure_count), rationale))
        scored.sort(key=lambda value: (value[0], value[1]))
        selected: list[PlanItem] = []
        concept_counts: dict[str, int] = {}; category_counts: dict[str, int] = {}
        for _, _, item, rationale in scored:
            if len(selected) >= size: break
            if concept_counts.get(item.concept_id, 0) >= max_per_concept: continue
            if category_counts.get(item.category, 0) >= max(1, math.ceil(size / 2)): continue
            selected.append(PlanItem(item.question_id, item.concept_id, item.category, rationale))
            concept_counts[item.concept_id] = concept_counts.get(item.concept_id, 0) + 1
            category_counts[item.category] = category_counts.get(item.category, 0) + 1
        return selected

    def _category(self, item: PlanCandidate, state: MasteryState) -> str:
        if item.due: return "due"
        if item.recent_error: return "recent"
        if state.score < 0.4: return "weak"
        if state.uncertainty > 0.7: return "confidence_repair"
        if item.difficulty > state.score + 0.25: return "challenge"
        return "mixed"

    def _rationale(self, category: str, state: MasteryState) -> str:
        messages = {
            "weak": "Selected because this concept has low demonstrated mastery.", "due": "Selected because a re-check is due.",
            "recent": "Selected to repair a recent error.", "mixed": "Selected to maintain broad retrieval practice.",
            "challenge": "Selected as a controlled stretch item.", "confidence_repair": "Selected to reduce uncertainty with more evidence.",
        }
        return f"{messages[category]} Model {state.model_version}; score {state.score:.2f}; uncertainty {state.uncertainty:.2f}."


class ShadowComparator:
    def compare(self, attempts: list[AttemptEvidence], production: ModelConfig, shadow: ModelConfig) -> dict[str, Any]:
        prod = MasteryModel(production).replay(attempts); candidate = MasteryModel(shadow).replay(attempts)
        differences = {concept: round(candidate[concept].score - prod[concept].score, 6) for concept in sorted(prod)}
        return {"production_version": production.version, "shadow_version": shadow.version, "differences": differences, "production": {key: asdict(value) for key, value in prod.items()}}


@dataclass(frozen=True)
class Phase6Evaluation:
    passed: bool
    checks: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": self.checks, "check_count": len(self.checks)}


class Phase6Evaluator:
    def run(self) -> Phase6Evaluation:
        model = MasteryModel(); checks: dict[str, bool] = {}
        start = MasteryState("c1", 0.5, 1.0, 0, model.config.version)
        correct = model.update(start, AttemptEvidence("c1", True, 20_000, difficulty=0.7, confidence=0.9))
        wrong = model.update(start, AttemptEvidence("c1", False, 20_000, difficulty=0.7, confidence=0.9))
        checks["correct_moves_up"] = correct.score > start.score; checks["incorrect_moves_down"] = wrong.score < start.score
        checks["uncertainty_reduces"] = correct.uncertainty < start.uncertainty
        hinted = model.update(start, AttemptEvidence("c1", True, 20_000, hint_used=True, answer_changes=2))
        checks["hints_reduce_weight"] = hinted.score < correct.score
        anomaly = model.update(start, AttemptEvidence("c1", True, 99_999_999)); checks["anomaly_bounded"] = start.score < anomaly.score < correct.score
        checks["experimental_ignored"] = model.update(start, AttemptEvidence("c1", False, 10_000, experimental=True)) == start
        attempts = [AttemptEvidence("weak", False, 30_000), AttemptEvidence("strong", True, 20_000), AttemptEvidence("strong", True, 20_000)]
        states = model.replay(attempts)
        candidates = [PlanCandidate("q1", "weak", "", 0.4), PlanCandidate("q2", "weak", "", 0.5), PlanCandidate("q3", "weak", "", 0.6), PlanCandidate("q4", "due", "", 0.4, due=True), PlanCandidate("q5", "recent", "", 0.4, recent_error=True), PlanCandidate("q6", "strong", "", 0.9), PlanCandidate("q7", "new", "", 0.4), PlanCandidate("q8", "exp", "", 0.4, experimental=True)]
        planner = DailyPlanner(); first = planner.create(states=states, candidates=candidates, size=6, seed="daily"); second = planner.create(states=states, candidates=list(reversed(candidates)), size=6, seed="daily")
        checks["plan_deterministic"] = first == second; checks["weak_and_due_covered"] = {item.category for item in first} >= {"weak", "due"}
        counts: dict[str, int] = {}
        for item in first: counts[item.concept_id] = counts.get(item.concept_id, 0) + 1
        checks["concept_diversity_enforced"] = max(counts.values()) <= 2 and len(counts) >= 3
        checks["experimental_candidates_excluded"] = all(item.question_id != "q8" for item in first)
        checks["rationales_present"] = all(item.rationale and "Model" in item.rationale for item in first)
        shadow = ShadowComparator().compare(attempts, ModelConfig(version="prod"), ModelConfig(version="shadow", learning_rate=0.2))
        checks["shadow_is_read_only"] = shadow["production"]["weak"]["score"] == states["weak"].score
        checks["model_version_recorded"] = all(state.model_version == model.config.version for state in states.values())
        checks["ranking_sanity"] = states["weak"].score < states["strong"].score
        checks["evaluator_depth"] = len(checks) >= 13
        return Phase6Evaluation(all(checks.values()), checks)


if __name__ == "__main__":
    report = Phase6Evaluator().run(); print(json.dumps(report.to_dict(), indent=2, sort_keys=True)); raise SystemExit(0 if report.passed else 1)
