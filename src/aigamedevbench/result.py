from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    expected: object = None
    actual: object = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "expected": self.expected,
            "actual": self.actual,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CheckResult":
        return cls(
            name=data["name"],
            passed=data["passed"],
            detail=data.get("detail", ""),
            expected=data.get("expected"),
            actual=data.get("actual"),
        )


@dataclass
class VerifierResult:
    score: float
    status: str
    checks: list[CheckResult] = field(default_factory=list)
    category: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "status": self.status,
            "category": self.category,
            "error": self.error,
            "checks": [c.to_dict() for c in self.checks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VerifierResult":
        return cls(
            score=data["score"],
            status=data["status"],
            checks=[CheckResult.from_dict(c) for c in data.get("checks", [])],
            category=data.get("category", ""),
            error=data.get("error", ""),
        )

    @classmethod
    def error_result(cls, category: str, message: str) -> "VerifierResult":
        return cls(score=0.0, status="error", checks=[], category=category, error=message)

    @classmethod
    def from_checks(cls, checks: list[CheckResult], category: str, mode: str) -> "VerifierResult":
        if mode == "tristate":
            return cls._tristate(checks, category)
        if mode == "weighted":
            total_w = sum(float(c.expected or 1.0) for c in checks) or 1.0
            got = sum(float(c.expected or 1.0) for c in checks if c.passed)
            score = got / total_w
            return cls(score=score, status=cls._status_from_score(score), checks=checks, category=category)
        if not checks:
            return cls(score=0.0, status="fail", checks=checks, category=category)
        passed = sum(1 for c in checks if c.passed)
        score = passed / len(checks)
        return cls(score=score, status=cls._status_from_score(score), checks=checks, category=category)

    @staticmethod
    def _status_from_score(score: float) -> str:
        if score >= 1.0:
            return "pass"
        if score <= 0.0:
            return "fail"
        return "partial"

    @classmethod
    def _tristate(cls, checks: list[CheckResult], category: str) -> "VerifierResult":
        by_name = {c.name: c for c in checks}
        intended = by_name.get("intended_change")
        side = by_name.get("no_side_effects")
        if intended is not None and not intended.passed:
            return cls(score=0.0, status="fail", checks=checks, category=category)
        if side is not None and not side.passed:
            return cls(score=0.5, status="partial", checks=checks, category=category)
        return cls(score=1.0, status="pass", checks=checks, category=category)
