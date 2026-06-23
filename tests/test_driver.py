from __future__ import annotations

import sys
from pathlib import Path

from aigamedevbench.driver import NoOpDriver, PatchDriver, CommandHarnessDriver


def test_noop_changes_nothing(tmp_path):
    (tmp_path / "f.txt").write_text("a\n", encoding="utf-8")
    NoOpDriver().run("task", tmp_path)
    assert (tmp_path / "f.txt").read_text(encoding="utf-8") == "a\n"


def test_patch_driver_applies(tmp_path):
    from aigamedevbench.git_ops import git_run
    git_run(["init"], cwd=tmp_path)
    git_run(["config", "user.email", "t@t.com"], cwd=tmp_path)
    git_run(["config", "user.name", "t"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("a\n", encoding="utf-8")
    git_run(["add", "f.txt"], cwd=tmp_path)
    git_run(["commit", "-m", "i"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("b\n", encoding="utf-8")
    patch = git_run(["diff"], cwd=tmp_path)
    git_run(["checkout", "f.txt"], cwd=tmp_path)
    PatchDriver(patch).run("task", tmp_path)
    assert (tmp_path / "f.txt").read_text(encoding="utf-8") == "b\n"


def _echo_argv_harness(out_file: Path) -> str:
    """A fake harness command template: a python one-liner that writes its
    own argv (everything after the script) to out_file, one arg per line."""
    script = (
        "import sys, pathlib; "
        f"pathlib.Path(r'{out_file}').write_text("
        "chr(10).join(sys.argv[1:]), encoding='utf-8')"
    )
    # {task} is passed as a single argv element after the script.
    return f'{sys.executable} -c "{script}" {{task}}'


def test_command_driver_writes_task_file(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    out = tmp_path / "argv.txt"
    drv = CommandHarnessDriver(_echo_argv_harness(out), timeout=30,
                               log_dir=tmp_path / "logs")
    drv.run("do the thing", ws)
    assert (ws / "TASK.md").read_text(encoding="utf-8") == "do the thing"


def test_command_driver_task_is_single_arg(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    out = tmp_path / "argv.txt"
    drv = CommandHarnessDriver(_echo_argv_harness(out), timeout=30,
                               log_dir=tmp_path / "logs")
    drv.run("multi word task", ws)
    # argv after the script is exactly ONE line: the whole task string.
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines == ["multi word task"]
