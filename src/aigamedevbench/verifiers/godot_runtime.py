from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from aigamedevbench.result import CheckResult, VerifierResult
from aigamedevbench.testcase import Testcase
from aigamedevbench.verifiers.base import register

_JSON_RE = re.compile(r'\{.*"assertions".*\}')


def parse_assertion_json(stdout: str) -> list[CheckResult]:
    match = _JSON_RE.search(stdout)
    if not match:
        return []
    data = json.loads(match.group(0))
    checks = []
    for a in data.get("assertions", []):
        checks.append(CheckResult(a["name"], bool(a["pass"]), detail=a.get("detail", "")))
    return checks


def _run_godot_script(testcase: Testcase, workspace: Path,
                      godot_binary: str = "godot", timeout: int = 30) -> VerifierResult:
    if shutil.which(godot_binary) is None:
        return VerifierResult.error_result(testcase.category, f"godot binary '{godot_binary}' not found")
    golden = testcase.dir / testcase.verifier_entry
    if not golden.exists():
        return VerifierResult.error_result(testcase.category, f"verifier script missing: {golden}")
    tmp_name = f".aigdbench_verify_{uuid.uuid4().hex}.gd"
    tmp_path = workspace / tmp_name
    tmp_path.write_text(golden.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        proc = subprocess.run(
            [godot_binary, "--headless", "--path", str(workspace),
             "--script", tmp_name],
            capture_output=True, text=True, timeout=timeout,
        )
        checks = parse_assertion_json(proc.stdout)
        if not checks:
            return VerifierResult.error_result(
                testcase.category,
                f"no assertion JSON in output (exit {proc.returncode}): {proc.stderr[:200]}")
        return VerifierResult.from_checks(checks, testcase.category, testcase.scoring_mode)
    except subprocess.TimeoutExpired:
        return VerifierResult.error_result(testcase.category, f"godot timed out after {timeout}s")
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@register("godot_scenetree")
class GodotSceneTreeVerifier:
    def verify(self, testcase: Testcase, workspace: Path) -> VerifierResult:
        return _run_godot_script(testcase, workspace)


@register("visual_static")
class VisualStaticVerifier:
    def verify(self, testcase: Testcase, workspace: Path) -> VerifierResult:
        # Structured layer only; screenshot/SSIM layer is a separate (deferred) plan.
        return _run_godot_script(testcase, workspace)


@register("interaction_routing")
class InteractionRoutingVerifier:
    """Click-routing + tab-order checks.

    Mechanism is identical to GodotSceneTreeVerifier: the golden .gd injects
    InputEventMouseButton at REFERENCE visual positions and walks the focus
    chain, then prints assertion JSON. CI SMOKE-TEST CAVEAT: confirm headless
    can route GUI input on the team CI image before relying on this verifier.
    """

    def verify(self, testcase: Testcase, workspace: Path) -> VerifierResult:
        return _run_godot_script(testcase, workspace)
