from __future__ import annotations

import os
import shutil
import stat
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from aigamedevbench.git_ops import git_run


def _rmtree(path: Path) -> None:
    """Remove a tree, clearing read-only bits (Windows keeps .git packs read-only)."""
    def on_error(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    shutil.rmtree(path, onerror=on_error)


@contextmanager
def isolated_workspace(repo_root: Path, baseline_ref: str) -> Iterator[Path]:
    work_dir = Path(tempfile.gettempdir()) / f"aigdbench_ws_{uuid.uuid4().hex}"
    git_run(["worktree", "add", "--detach", str(work_dir), baseline_ref], cwd=repo_root)
    try:
        yield work_dir
    finally:
        try:
            git_run(["worktree", "remove", "--force", str(work_dir)], cwd=repo_root)
        except Exception:
            if work_dir.exists():
                shutil.rmtree(work_dir, ignore_errors=True)


@contextmanager
def folder_workspace(baseline_dir: Path) -> Iterator[Path]:
    """Workspace for folder-type testcases: copy a self-contained project dir,
    init a throwaway git repo so the driver (git apply) and change detection
    (git status) work the same as the git-worktree path."""
    if not baseline_dir.is_dir():
        raise FileNotFoundError(f"baseline dir not found: {baseline_dir}")
    work_dir = Path(tempfile.gettempdir()) / f"aigdbench_ws_{uuid.uuid4().hex}"
    shutil.copytree(baseline_dir, work_dir)
    git_run(["init", "-q"], cwd=work_dir)
    git_run(["add", "-A"], cwd=work_dir)
    git_run(
        ["-c", "user.email=bench@aigdbench.local", "-c", "user.name=aigdbench",
         "commit", "-q", "-m", "baseline"],
        cwd=work_dir,
    )
    try:
        yield work_dir
    finally:
        if work_dir.exists():
            _rmtree(work_dir)


def apply_patch(workspace: Path, patch_text: str) -> None:
    git_run(["apply", "--whitespace=nowarn", "-"], cwd=workspace, input=patch_text)
