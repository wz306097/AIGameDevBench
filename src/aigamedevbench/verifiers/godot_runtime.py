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
_VALIDATION_PASSED_RE = re.compile(r"VALIDATION_PASSED(?::\s*(.+))?")
_VALIDATION_FAILED_RE = re.compile(r"VALIDATION_FAILED(?::\s*(.+))?")


def parse_assertion_json(stdout: str) -> list[CheckResult]:
    match = _JSON_RE.search(stdout)
    if not match:
        return []
    data = json.loads(match.group(0))
    checks = []
    for a in data.get("assertions", []):
        checks.append(CheckResult(a["name"], bool(a["pass"]), detail=a.get("detail", "")))
    return checks


def parse_validation_marker(stdout: str) -> list[CheckResult]:
    """Fallback for GameDevBench-style golden verifiers that print a single
    VALIDATION_PASSED/FAILED line instead of per-assertion JSON. Yields one
    overall checkpoint (pass/fail). Returns [] if no marker is present."""
    for line in stdout.splitlines():
        line = line.strip()
        m = _VALIDATION_PASSED_RE.search(line)
        if m:
            return [CheckResult("validation", True, detail=(m.group(1) or "").strip())]
        m = _VALIDATION_FAILED_RE.search(line)
        if m:
            return [CheckResult("validation", False, detail=(m.group(1) or "").strip())]
    return []


def parse_scene_output(stdout: str) -> list[CheckResult]:
    """Per-assertion JSON if present, else the single VALIDATION_* marker."""
    checks = parse_assertion_json(stdout)
    if checks:
        return checks
    return parse_validation_marker(stdout)


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


def _run_godot_scene(testcase: Testcase, workspace: Path,
                     godot_binary: str = "godot", timeout: int = 60) -> VerifierResult:
    """Run a verifier in SCENE mode (not --script).

    Unlike _run_godot_script, this boots the project's main loop via a scene,
    so autoload singletons (e.g. a globally-named QuestManager) are available
    to the code under test. The testcase carries two files alongside
    verifier_entry (the scene): the scene file and a sibling `verifier.gd`.
    Both are injected into the workspace, run, then removed.
    """
    if shutil.which(godot_binary) is None:
        return VerifierResult.error_result(testcase.category, f"godot binary '{godot_binary}' not found")
    scene_src = testcase.dir / testcase.verifier_entry
    gd_src = testcase.dir / "verifier.gd"
    if not scene_src.exists():
        return VerifierResult.error_result(testcase.category, f"verifier scene missing: {scene_src}")
    if not gd_src.exists():
        return VerifierResult.error_result(testcase.category, f"verifier.gd missing: {gd_src}")

    suffix = uuid.uuid4().hex
    scene_name = f".aigdbench_verify_{suffix}.tscn"
    gd_name = f".aigdbench_verify_{suffix}.gd"
    scene_path = workspace / scene_name
    gd_path = workspace / gd_name
    # The scene references the script by its res:// basename; rewrite the
    # placeholder script path so injected scene + script names line up.
    scene_text = scene_src.read_text(encoding="utf-8").replace("__VERIFIER_GD__", gd_name)
    scene_path.write_text(scene_text, encoding="utf-8")
    gd_path.write_text(gd_src.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        proc = subprocess.run(
            [godot_binary, "--headless", "--path", str(workspace), scene_name],
            capture_output=True, text=True, timeout=timeout,
        )
        checks = parse_scene_output(proc.stdout)
        if not checks:
            return VerifierResult.error_result(
                testcase.category,
                f"no assertion JSON in output (exit {proc.returncode}): {proc.stderr[:200]}")
        return VerifierResult.from_checks(checks, testcase.category, testcase.scoring_mode)
    except subprocess.TimeoutExpired:
        return VerifierResult.error_result(testcase.category, f"godot timed out after {timeout}s")
    finally:
        for p in (scene_path, gd_path):
            if p.exists():
                p.unlink()


@register("godot_scenetree")
class GodotSceneTreeVerifier:
    def verify(self, testcase: Testcase, workspace: Path) -> VerifierResult:
        return _run_godot_script(testcase, workspace)


@register("godot_scene_assert")
class GodotSceneAssertVerifier:
    """Scene-mode verifier for imported GameDevBench-style tasks.

    Boots a scene so autoload singletons load, runs the converted verifier.gd
    which prints {"assertions":[...]}, and scores per-checkpoint.
    """

    def verify(self, testcase: Testcase, workspace: Path) -> VerifierResult:
        return _run_godot_scene(testcase, workspace)


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
