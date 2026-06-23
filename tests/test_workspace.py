from __future__ import annotations

from pathlib import Path

import pytest

from aigamedevbench.workspace import isolated_workspace, folder_workspace, apply_patch
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


def _make_baseline(path: Path) -> None:
    (path / "scripts").mkdir(parents=True, exist_ok=True)
    (path / "scripts" / "main.gd").write_text("extends Node\n", encoding="utf-8")


def test_folder_workspace_copies_and_inits_git(tmp_path):
    baseline = tmp_path / "baseline"
    _make_baseline(baseline)
    captured = {}
    with folder_workspace(baseline) as ws:
        assert (ws / "scripts" / "main.gd").read_text(encoding="utf-8") == "extends Node\n"
        # fresh git repo with a clean tree (no changes yet)
        status = git_run(["status", "--porcelain"], cwd=ws)
        assert status.strip() == ""
        captured["ws"] = ws
    assert not captured["ws"].exists()


def test_folder_workspace_changes_are_visible(tmp_path):
    baseline = tmp_path / "baseline"
    _make_baseline(baseline)
    with folder_workspace(baseline) as ws:
        (ws / "scripts" / "main.gd").write_text("extends Node\n# edit\n", encoding="utf-8")
        status = git_run(["status", "--porcelain"], cwd=ws)
        assert "scripts/main.gd" in status
    # baseline itself is untouched
    assert (baseline / "scripts" / "main.gd").read_text(encoding="utf-8") == "extends Node\n"


def test_folder_workspace_apply_patch(tmp_path):
    baseline = tmp_path / "baseline"
    _make_baseline(baseline)
    patch = (
        "diff --git a/scripts/main.gd b/scripts/main.gd\n"
        "--- a/scripts/main.gd\n"
        "+++ b/scripts/main.gd\n"
        "@@ -1 +1,2 @@\n"
        " extends Node\n"
        "+# patched\n"
    )
    with folder_workspace(baseline) as ws:
        apply_patch(ws, patch)
        assert "# patched" in (ws / "scripts" / "main.gd").read_text(encoding="utf-8")


def test_folder_workspace_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        with folder_workspace(tmp_path / "nope"):
            pass
