from __future__ import annotations

from aigamedevbench.result import CheckResult, VerifierResult


def test_checkpoints_mode_partial_score():
    checks = [CheckResult("a", True), CheckResult("b", True), CheckResult("c", False)]
    r = VerifierResult.from_checks(checks, category="behavior_logic", mode="checkpoints")
    assert abs(r.score - 2 / 3) < 1e-9
    assert r.status == "partial"


def test_checkpoints_all_pass():
    checks = [CheckResult("a", True), CheckResult("b", True)]
    r = VerifierResult.from_checks(checks, category="behavior_logic", mode="checkpoints")
    assert r.score == 1.0
    assert r.status == "pass"


def test_tristate_side_effect_is_partial():
    checks = [CheckResult("intended_change", True), CheckResult("no_side_effects", False)]
    r = VerifierResult.from_checks(checks, category="precise_edit", mode="tristate")
    assert r.status == "partial"
    assert 0.0 < r.score < 1.0


def test_tristate_intended_missing_is_fail():
    checks = [CheckResult("intended_change", False), CheckResult("no_side_effects", True)]
    r = VerifierResult.from_checks(checks, category="precise_edit", mode="tristate")
    assert r.status == "fail"
    assert r.score == 0.0


def test_roundtrip():
    r = VerifierResult.from_checks([CheckResult("a", True)], "behavior_logic", "checkpoints")
    assert VerifierResult.from_dict(r.to_dict()).to_dict() == r.to_dict()
