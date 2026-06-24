from __future__ import annotations

import json
from pathlib import Path

from aigamedevbench.driver import NoOpDriver, PatchDriver
from aigamedevbench.runner import run_testcase
from aigamedevbench.testcase import Testcase
from aigamedevbench.git_ops import git_run


def _make_repo_with_config(tmp_path) -> tuple[Path, str]:
    repo = tmp_path / "repo"; repo.mkdir()
    git_run(["init"], cwd=repo)
    git_run(["config", "user.email", "t@t.com"], cwd=repo)
    git_run(["config", "user.name", "t"], cwd=repo)
    (repo / "data").mkdir()
    (repo / "data" / "char.json").write_text(json.dumps({"attack": 50}) + "\n", encoding="utf-8")
    git_run(["add", "."], cwd=repo)
    git_run(["commit", "-m", "baseline"], cwd=repo)
    head = git_run(["rev-parse", "HEAD"], cwd=repo).strip()
    return repo, head


def _config_testcase(tmp_path, head) -> Testcase:
    tc_dir = tmp_path / "tc"; tc_dir.mkdir()
    (tc_dir / "expected.json").write_text(json.dumps({"fields": [
        {"name": "attack", "aliases": ["attack"], "files_glob": "**/*.json",
         "expected": 60, "tol": 1e-6, "base": 50, "must_differ_from_base": True},
    ]}), encoding="utf-8")
    return Testcase("bench-x", "intent_translation", head,
                    "Set attack to base+20%", "py_config", "verify.py", "fields", tc_dir)


def test_noop_driver_fails_intent(tmp_path):
    repo, head = _make_repo_with_config(tmp_path)
    tc = _config_testcase(tmp_path, head)
    result = run_testcase(repo, tc, NoOpDriver(), "noop", config={})
    assert result.score == 0.0
    assert result.verifier_result.status in ("fail", "partial")


def test_correct_patch_passes(tmp_path):
    repo, head = _make_repo_with_config(tmp_path)
    tc = _config_testcase(tmp_path, head)
    patch = (
        "diff --git a/data/char.json b/data/char.json\n"
        "--- a/data/char.json\n"
        "+++ b/data/char.json\n"
        "@@ -1 +1 @@\n"
        '-{"attack": 50}\n'
        '+{"attack": 60}\n'
    )
    result = run_testcase(repo, tc, PatchDriver(patch), "patch", config={})
    assert result.score == 1.0
    assert result.verifier_result.status == "pass"


def _folder_testcase(tmp_path) -> Testcase:
    """A folder-type testcase using the pure-Python py_config verifier, so the
    runner's folder_workspace branch can be exercised without a Godot binary."""
    tc_dir = tmp_path / "tc-folder"
    baseline = tc_dir / "baseline"
    (baseline / "data").mkdir(parents=True)
    (baseline / "data" / "char.json").write_text(json.dumps({"attack": 50}) + "\n", encoding="utf-8")
    (tc_dir / "expected.json").write_text(json.dumps({"fields": [
        {"name": "attack", "aliases": ["attack"], "files_glob": "**/*.json",
         "expected": 60, "tol": 1e-6, "base": 50, "must_differ_from_base": True},
    ]}), encoding="utf-8")
    return Testcase("gdb-x", "behavior_logic", "", "task", "py_config",
                    "expected.json", "fields", tc_dir, source_kind="folder")


def test_folder_testcase_uses_folder_workspace(tmp_path):
    tc = _folder_testcase(tmp_path)
    # repo_root is None: folder-type must not need a game repo.
    result = run_testcase(None, tc, NoOpDriver(), "noop", config={})
    assert result.score == 0.0

    patch = (
        "diff --git a/data/char.json b/data/char.json\n"
        "--- a/data/char.json\n"
        "+++ b/data/char.json\n"
        "@@ -1 +1 @@\n"
        '-{"attack": 50}\n'
        '+{"attack": 60}\n'
    )
    result = run_testcase(None, tc, PatchDriver(patch), "patch", config={})
    assert result.score == 1.0
    assert result.verifier_result.status == "pass"
