from __future__ import annotations

from pathlib import Path

import pytest

from aigamedevbench.result import CheckResult, VerifierResult
from aigamedevbench.testcase import Testcase
from aigamedevbench.verifiers.base import register, get_verifier


def test_register_and_get():
    @register("dummy_type_for_test")
    class _Dummy:
        def verify(self, testcase, workspace):
            return VerifierResult.from_checks([CheckResult("x", True)], "behavior_logic", "checkpoints")

    v = get_verifier("dummy_type_for_test")
    tc = Testcase("id", "behavior_logic", "ref", "task", "dummy_type_for_test", "v.gd", "checkpoints", Path("."))
    result = v.verify(tc, Path("."))
    assert result.status == "pass"


def test_unknown_type_raises():
    with pytest.raises(KeyError):
        get_verifier("does_not_exist")
