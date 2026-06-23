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
    assert drv.last_outcome["exit_code"] == 0
    assert out.exists()


def test_command_driver_task_is_single_arg(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    out = tmp_path / "argv.txt"
    drv = CommandHarnessDriver(_echo_argv_harness(out), timeout=30,
                               log_dir=tmp_path / "logs")
    drv.run("multi word task", ws)
    # argv after the script is exactly ONE line: the whole task string.
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines == ["multi word task"]


def test_command_driver_records_outcome(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    out = tmp_path / "argv.txt"
    drv = CommandHarnessDriver(_echo_argv_harness(out), timeout=30,
                               log_dir=tmp_path / "logs")
    drv.label = "tc-1"
    drv.run("task", ws)
    o = drv.last_outcome
    assert set(o) == {"exit_code", "wall_time", "timed_out", "log_path"}
    assert o["exit_code"] == 0
    assert o["timed_out"] is False
    assert o["wall_time"] >= 0.0
    assert Path(o["log_path"]).exists()


def test_command_driver_nonzero_exit_does_not_raise(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    cmd = f'{sys.executable} -c "import sys; sys.exit(3)"'
    drv = CommandHarnessDriver(cmd, timeout=30, log_dir=tmp_path / "logs")
    drv.run("task", ws)  # must not raise
    assert drv.last_outcome["exit_code"] == 3
    assert drv.last_outcome["timed_out"] is False


def test_command_driver_timeout_is_killed(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    cmd = f'{sys.executable} -c "import time; time.sleep(30)"'
    drv = CommandHarnessDriver(cmd, timeout=1, log_dir=tmp_path / "logs")
    drv.run("task", ws)  # must not raise, returns quickly after kill
    assert drv.last_outcome["timed_out"] is True
    assert drv.last_outcome["exit_code"] == -1


def test_command_driver_missing_binary_does_not_raise(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    drv = CommandHarnessDriver("definitely-not-a-real-binary-xyz {task}",
                               timeout=30, log_dir=tmp_path / "logs")
    drv.run("task", ws)  # must not raise
    assert drv.last_outcome["exit_code"] == -1
    assert drv.last_outcome["timed_out"] is False


def test_command_driver_produces_detected_change(tmp_path):
    from aigamedevbench.git_ops import git_run
    ws = tmp_path / "ws"; ws.mkdir()
    git_run(["init"], cwd=ws)
    git_run(["config", "user.email", "t@t.com"], cwd=ws)
    git_run(["config", "user.name", "t"], cwd=ws)
    (ws / "f.txt").write_text("a\n", encoding="utf-8")
    git_run(["add", "f.txt"], cwd=ws)
    git_run(["commit", "-m", "i"], cwd=ws)
    script = "import pathlib; pathlib.Path('made.txt').write_text('x')"
    cmd = f'{sys.executable} -c "{script}"'
    drv = CommandHarnessDriver(cmd, timeout=30, log_dir=tmp_path / "logs")
    drv.run("task", ws)
    status = git_run(["status", "--porcelain"], cwd=ws)
    assert "made.txt" in status


def test_command_driver_no_shell_injection(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    canary = ws / "canary.txt"
    canary.write_text("alive", encoding="utf-8")
    out = tmp_path / "argv.txt"
    drv = CommandHarnessDriver(_echo_argv_harness(out), timeout=30,
                               log_dir=tmp_path / "logs")
    # If the task were ever interpolated into a shell, this would delete canary.
    # Use platform-specific shell command so the test is probative on all platforms.
    if sys.platform == "win32":
        payload = f"& del {canary}"      # cmd.exe command separator + delete
    else:
        payload = f"; rm -rf {canary}"   # POSIX shell separator + delete
    drv.run(payload, ws)
    assert canary.read_text(encoding="utf-8") == "alive"
    # And the malicious string arrives intact as one argv element.
    assert out.read_text(encoding="utf-8").splitlines() == [payload]
