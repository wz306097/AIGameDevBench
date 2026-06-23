from __future__ import annotations

from pathlib import Path

from aigamedevbench.workspace import isolated_workspace
from aigamedevbench.git_ops import git_run


def _init_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    git_run(["init"], cwd=path)
    git_run(["config", "user.email", "t@t.com"], cwd=path)
    git_run(["config", "user.name", "t"], cwd=path)
    (path / "file.txt").write_text("hello\n", encoding="utf-8")
    git_run(["add", "file.txt"], cwd=path)
    git_run(["commit", "-m", "init"], cwd=path)
    return git_run(["rev-parse", "HEAD"], cwd=path).strip()


def test_worktree_created_and_removed(tmp_path):
    repo = tmp_path / "repo"
    head = _init_repo(repo)
    captured = {}
    with isolated_workspace(repo, head) as ws:
        assert (ws / "file.txt").read_text(encoding="utf-8") == "hello\n"
        captured["ws"] = ws
        assert ws.exists()
    assert not captured["ws"].exists()


def test_changes_in_worktree_isolated(tmp_path):
    repo = tmp_path / "repo"
    head = _init_repo(repo)
    with isolated_workspace(repo, head) as ws:
        (ws / "file.txt").write_text("changed\n", encoding="utf-8")
    assert (repo / "file.txt").read_text(encoding="utf-8") == "hello\n"
