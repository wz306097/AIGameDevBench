from __future__ import annotations

import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Protocol

from aigamedevbench.workspace import apply_patch


class HarnessDriver(Protocol):
    def run(self, task: str, workspace: Path) -> None: ...


class NoOpDriver:
    def run(self, task: str, workspace: Path) -> None:
        return None


class PatchDriver:
    def __init__(self, patch_text: str):
        self.patch_text = patch_text

    def run(self, task: str, workspace: Path) -> None:
        apply_patch(workspace, self.patch_text)


class CommandHarnessDriver:
    """Runs an arbitrary CLI harness inside the workspace to complete the task.

    The command template is shlex-split (template paths should use forward slashes
    on Windows), then each token has placeholders substituted: {task} (raw task
    text as a single arg), {task_file} (path to workspace/TASK.md), {workspace}
    (workspace path). No shell is used, so the task text can contain any
    characters without injection risk.
    """

    def __init__(self, cmd_template: str, timeout: float = 600.0,
                 log_dir: Path | None = None):
        self.cmd_template = cmd_template
        self.timeout = timeout
        self.log_dir = Path(log_dir) if log_dir is not None else None
        self.label = ""
        self.last_outcome: dict | None = None
        self._counter = 0

    def _build_argv(self, task: str, task_file: Path, workspace: Path) -> list[str]:
        repl = {
            "{task}": task,
            "{task_file}": str(task_file),
            "{workspace}": str(workspace),
        }
        # Single-pass substitution: only placeholders present in the ORIGINAL
        # template token are replaced, so substituted values that happen to
        # contain a placeholder literal (e.g. a task mentioning "{workspace}")
        # are not re-scanned and mangled.
        pattern = re.compile("|".join(re.escape(k) for k in repl))
        # shlex.split() runs in POSIX mode and would treat backslashes as escapes,
        # mangling Windows paths in the template (e.g. sys.executable). Normalize the
        # template (NOT the substituted values) to forward slashes; placeholders are
        # filled in after the split, so task content and injection-safety are unaffected.
        # Limitation: every backslash in the template is treated as a path separator, so
        # backslashes that are NOT path separators (UNC paths like \\server\share, or
        # regex escapes) will be altered — pass those via a wrapper script or use forward slashes.
        return [
            pattern.sub(lambda m: repl[m.group(0)], token)
            for token in shlex.split(self.cmd_template.replace("\\", "/"))
        ]

    def _log_path(self, workspace: Path) -> Path | None:
        if self.log_dir is None:
            return None
        self.log_dir.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_"
                       for c in (self.label or "run"))
        self._counter += 1
        return self.log_dir / f"{self._counter:04d}-{safe}.log"

    def run(self, task: str, workspace: Path) -> None:
        workspace = Path(workspace)
        start = time.perf_counter()
        exit_code = 0
        timed_out = False
        stdout = stderr = ""
        argv: list[str] = []
        log_path = None
        try:
            # Inside the try so a malformed template (shlex.split ValueError),
            # an unwritable workspace, or a log-dir mkdir failure is recorded as
            # a failed outcome rather than propagating and aborting the batch.
            task_file = workspace / "TASK.md"
            task_file.write_text(task, encoding="utf-8")
            argv = self._build_argv(task, task_file, workspace)
            log_path = self._log_path(workspace)
            proc = subprocess.run(
                argv, cwd=str(workspace), timeout=self.timeout,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            exit_code = proc.returncode
            stdout, stderr = proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as e:
            timed_out = True
            exit_code = -1
            stdout = e.stdout or ""
            stderr = (e.stderr or "") + "\n[TIMEOUT]"
        except FileNotFoundError as e:
            exit_code = -1
            stderr = f"[harness binary not found] {e}"
        except Exception as e:  # never propagate to the batch loop
            exit_code = -1
            stderr = f"[driver error] {e!r}"
        wall_time = time.perf_counter() - start

        if log_path is not None:
            log_path.write_text(
                f"$ {' '.join(argv)}\n"
                f"exit_code={exit_code} timed_out={timed_out} "
                f"wall_time={wall_time:.3f}\n"
                f"--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n",
                encoding="utf-8",
            )

        self.last_outcome = {
            "exit_code": exit_code,
            "wall_time": wall_time,
            "timed_out": timed_out,
            "log_path": str(log_path) if log_path is not None else None,
        }
