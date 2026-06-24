from __future__ import annotations

import json
import sys

from click.testing import CliRunner

from aigamedevbench.cli import main
from aigamedevbench.git_ops import git_run


def _repo_and_testcases(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    git_run(["init"], cwd=repo)
    git_run(["config", "user.email", "t@t.com"], cwd=repo)
    git_run(["config", "user.name", "t"], cwd=repo)
    (repo / "data").mkdir()
    (repo / "data" / "char.json").write_text(json.dumps({"attack": 50}) + "\n", encoding="utf-8")
    git_run(["add", "."], cwd=repo)
    git_run(["commit", "-m", "baseline"], cwd=repo)
    head = git_run(["rev-parse", "HEAD"], cwd=repo).strip()

    tcs = tmp_path / "testcases"
    tc = tcs / "bench-0001"; tc.mkdir(parents=True)
    (tc / "testcase.toml").write_text(f"""
[testcase]
id = "bench-0001"
category = "intent_translation"
baseline_ref = "{head}"
task = "set attack"

[verifier]
type = "py_config"
entry = "verify.py"

[scoring]
mode = "fields"
""", encoding="utf-8")
    (tc / "expected.json").write_text(json.dumps({"fields": [
        {"name": "attack", "aliases": ["attack"], "files_glob": "**/*.json",
         "expected": 60, "tol": 1e-6, "base": 50, "must_differ_from_base": True},
    ]}), encoding="utf-8")
    return repo, tcs


def test_list(tmp_path):
    repo, tcs = _repo_and_testcases(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--testcases-dir", str(tcs)])
    assert result.exit_code == 0
    assert "bench-0001" in result.output
    assert "intent_translation" in result.output


def test_run_noop_fails(tmp_path, monkeypatch):
    repo, tcs = _repo_and_testcases(tmp_path)
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(main, ["run", "--testcases-dir", str(tcs), "--driver", "noop"])
    assert result.exit_code == 0
    assert "bench-0001" in result.output
    assert "fail" in result.output.lower()


def test_run_command_driver_writes_report(tmp_path, monkeypatch):
    repo, tcs = _repo_and_testcases(tmp_path)
    monkeypatch.chdir(repo)
    # A fake harness that sets attack to 60 by overwriting the json file.
    script = (
        "import pathlib, json; "
        "p=pathlib.Path('data/char.json'); "
        "p.write_text(json.dumps({'attack': 60})+chr(10))"
    )
    cmd = f'{sys.executable} -c "{script}"'
    report = tmp_path / "report.json"
    runner = CliRunner()
    result = runner.invoke(main, [
        "run", "--testcases-dir", str(tcs),
        "--driver", "command",
        "--harness-cmd", cmd,
        "--harness", "fake-harness",
        "--timeout", "60",
        "--log-dir", str(tmp_path / "logs"),
        "--report", str(report),
    ])
    assert result.exit_code == 0, result.output
    assert "bench-0001" in result.output
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["harness"] == "fake-harness"
    assert data["count"] == 1
    assert data["mean_score"] == 1.0
    tc0 = data["testcases"][0]
    assert tc0["score"] == 1.0
    assert "wall_time" in tc0 and "exit_code" in tc0 and "log_path" in tc0 and "timed_out" in tc0
    assert tc0["exit_code"] == 0


def test_run_git_testcase_from_non_git_cwd_does_not_abort_batch(tmp_path, monkeypatch):
    # Regression: a git-type testcase scored from a non-git cwd used to make
    # get_repo_root exit 128 and abort the whole batch before any folder-type
    # testcase ran. Now the git-type case errors individually and the batch
    # continues.
    repo, tcs = _repo_and_testcases(tmp_path)

    # Add a self-contained folder-type testcase alongside the git-type one.
    folder_tc = tcs / "folder-0001"; folder_tc.mkdir()
    (folder_tc / "testcase.toml").write_text("""
[testcase]
id = "folder-0001"
category = "intent_translation"
source_kind = "folder"
task = "set attack"

[verifier]
type = "py_config"
entry = "expected.json"

[scoring]
mode = "fields"
""", encoding="utf-8")
    (folder_tc / "expected.json").write_text(json.dumps({"fields": [
        {"name": "attack", "aliases": ["attack"], "files_glob": "**/*.json",
         "expected": 60, "tol": 1e-6, "base": 50, "must_differ_from_base": True},
    ]}), encoding="utf-8")
    baseline = folder_tc / "baseline"; (baseline / "data").mkdir(parents=True)
    (baseline / "data" / "char.json").write_text(json.dumps({"attack": 50}) + "\n", encoding="utf-8")

    non_git = tmp_path / "elsewhere"; non_git.mkdir()
    monkeypatch.chdir(non_git)
    runner = CliRunner()
    result = runner.invoke(main, ["run", "--testcases-dir", str(tcs), "--driver", "noop"])

    assert result.exit_code == 0, result.output
    # git-type testcase reports an error row instead of crashing the run
    assert "bench-0001" in result.output
    assert "error" in result.output.lower()
    # folder-type testcase still ran (noop -> fail, not skipped)
    assert "folder-0001" in result.output


def test_run_command_driver_echoes_failure_log(tmp_path, monkeypatch):
    # A non-zero harness exit must surface its log tail on screen, not just in a
    # file, so the user sees what broke immediately.
    repo, tcs = _repo_and_testcases(tmp_path)
    monkeypatch.chdir(repo)
    script = "import sys; print('BOOM diagnostic'); sys.exit(3)"
    cmd = f'{sys.executable} -c "{script}"'
    runner = CliRunner()
    result = runner.invoke(main, [
        "run", "--testcases-dir", str(tcs),
        "--driver", "command", "--harness-cmd", cmd,
        "--log-dir", str(tmp_path / "logs"),
    ])
    assert result.exit_code == 0, result.output
    assert "exit_code=3" in result.output
    assert "BOOM diagnostic" in result.output


def test_run_honors_workspace_root(tmp_path, monkeypatch):
    # --workspace-root must place the per-testcase workspace under the given dir
    # (so a harness that distrusts the OS temp path can run without hanging).
    repo, tcs = _repo_and_testcases(tmp_path)
    monkeypatch.chdir(repo)
    wsroot = tmp_path / "trusted_ws"
    # A fake harness that records its own cwd (== the workspace) into a file
    # under the repo, so we can assert where the workspace was created.
    marker = tmp_path / "where.txt"
    script = (
        "import os, pathlib; "
        f"pathlib.Path(r'{marker}').write_text(os.getcwd())"
    )
    cmd = f'{sys.executable} -c "{script}"'
    runner = CliRunner()
    result = runner.invoke(main, [
        "run", "--testcases-dir", str(tcs),
        "--driver", "command", "--harness-cmd", cmd,
        "--log-dir", str(tmp_path / "logs"),
        "--workspace-root", str(wsroot),
    ])
    assert result.exit_code == 0, result.output
    where = marker.read_text(encoding="utf-8")
    assert str(wsroot) in where, where


def test_run_command_driver_requires_cmd(tmp_path, monkeypatch):
    repo, tcs = _repo_and_testcases(tmp_path)
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(main, [
        "run", "--testcases-dir", str(tcs), "--driver", "command",
    ])
    assert result.exit_code == 0
    assert "harness-cmd" in result.output.lower()
