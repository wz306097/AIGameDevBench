from __future__ import annotations

import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from aigamedevbench.git_ops import git_run


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


def apply_patch(workspace: Path, patch_text: str) -> None:
    git_run(["apply", "--whitespace=nowarn", "-"], cwd=workspace, input=patch_text)
