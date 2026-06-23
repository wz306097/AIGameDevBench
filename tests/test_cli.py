from __future__ import annotations

import json

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
