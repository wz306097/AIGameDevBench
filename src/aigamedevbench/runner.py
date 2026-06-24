from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aigamedevbench.driver import HarnessDriver
from aigamedevbench.result import VerifierResult
from aigamedevbench.testcase import Testcase
from aigamedevbench.verifiers.base import get_verifier
from aigamedevbench.workspace import isolated_workspace, folder_workspace
from aigamedevbench.validation import run_validation
from contextlib import contextmanager

# Import verifiers package so all @register decorators run.
import aigamedevbench.verifiers  # noqa: F401


@dataclass
class RunResult:
    testcase_id: str
    harness: str
    category: str
    l0_l1_pass: bool
    verifier_result: VerifierResult
    score: float

    def to_dict(self) -> dict:
        return {
            "testcase_id": self.testcase_id,
            "harness": self.harness,
            "category": self.category,
            "l0_l1_pass": self.l0_l1_pass,
            "score": self.score,
            "verifier_result": self.verifier_result.to_dict(),
        }


@contextmanager
def _workspace_for(repo_root: Path | None, testcase: Testcase,
                   workspace_root: Path | str | None = None):
    if testcase.source_kind == "folder":
        with folder_workspace(testcase.dir / "baseline", workspace_root) as ws:
            yield ws
    else:
        if repo_root is None:
            raise ValueError(f"git-type testcase '{testcase.id}' requires a repo root")
        with isolated_workspace(repo_root, testcase.baseline_ref, workspace_root) as ws:
            yield ws


def run_testcase(repo_root: Path | None, testcase: Testcase, driver: HarnessDriver,
                 harness_id: str, config: dict | None = None,
                 workspace_root: Path | str | None = None) -> RunResult:
    config = config or {}
    with _workspace_for(repo_root, testcase, workspace_root) as workspace:
        driver.run(testcase.task, workspace)

        changed_files = _list_changed(workspace)
        verification = run_validation(workspace, changed_files, config)
        gate_pass = verification.l0_pass and verification.l1_pass

        if not gate_pass:
            failed = VerifierResult(score=0.0, status="fail", checks=[],
                                    category=testcase.category,
                                    error="L0/L1 gate failed")
            return RunResult(testcase.id, harness_id, testcase.category,
                             False, failed, 0.0)

        verifier = get_verifier(testcase.verifier_type)
        vr = verifier.verify(testcase, workspace)
        score = 0.0 if vr.status == "error" else vr.score
        return RunResult(testcase.id, harness_id, testcase.category,
                         True, vr, score)


def _list_changed(workspace: Path) -> list[str]:
    from aigamedevbench.git_ops import git_run
    out = git_run(["status", "--porcelain"], cwd=workspace)
    files = []
    for line in out.splitlines():
        if len(line) > 3:
            files.append(line[3:].strip())
    return files
