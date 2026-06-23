from __future__ import annotations

from pathlib import Path
from typing import Protocol

from aigamedevbench.result import VerifierResult
from aigamedevbench.testcase import Testcase

_REGISTRY: dict[str, "Verifier"] = {}


class Verifier(Protocol):
    def verify(self, testcase: Testcase, workspace: Path) -> VerifierResult: ...


def register(verifier_type: str):
    def deco(cls):
        _REGISTRY[verifier_type] = cls()
        return cls
    return deco


def get_verifier(verifier_type: str) -> Verifier:
    if verifier_type not in _REGISTRY:
        raise KeyError(f"no verifier registered for '{verifier_type}'")
    return _REGISTRY[verifier_type]
