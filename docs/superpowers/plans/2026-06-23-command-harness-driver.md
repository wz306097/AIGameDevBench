# Command Harness Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `CommandHarnessDriver` plus CLI wiring so AIGameDevBench can run an arbitrary AI coding CLI against testcases automatically and emit a JSON report.

**Architecture:** A new driver writes the testcase `task` to `workspace/TASK.md`, substitutes `{task}`/`{task_file}`/`{workspace}` placeholders into a `shlex`-split command template (token-level, no shell → no injection), runs it with `subprocess.run` inside the isolated workspace under a timeout, captures output to a log file, and records execution metadata in `last_outcome`. The existing runner detects the harness's file changes via `git status` and scores them with the frozen verifier — unchanged. The CLI gains a `command` driver choice and aggregates per-testcase results (including wall_time/exit_code) into an optional JSON report.

**Tech Stack:** Python ≥3.10, `click` (CLI), `subprocess`/`shlex`/`time` (stdlib), `pytest` (tests).

## Global Constraints

- Python ≥ 3.10 (per `README.md`).
- `subprocess` must run with `shell=False`; placeholder substitution is token-level on the `shlex.split` output. Never build a shell string from `task`.
- The `HarnessDriver` Protocol signature `run(self, task: str, workspace: Path) -> None` must NOT change. `NoOpDriver` and `PatchDriver` must NOT change.
- `runner.py`, `RunResult`, and the verifiers must NOT change.
- No absolute wall-clock in log filenames or anywhere that would break determinism; durations use `time.perf_counter()` deltas only.
- The driver must NEVER raise out of `run()` — all failure modes (missing binary, timeout, non-zero exit, any exception) are caught and recorded so the batch loop continues.

---

### Task 1: `CommandHarnessDriver` core (write task, substitute, run, record)

**Files:**
- Modify: `src/aigamedevbench/driver.py` (append a new class; leave existing classes untouched)
- Test: `tests/test_driver.py` (append tests)

**Interfaces:**
- Consumes: nothing from other tasks. Uses stdlib `subprocess`, `shlex`, `time`, `pathlib.Path`.
- Produces:
  - `CommandHarnessDriver(cmd_template: str, timeout: float = 600.0, log_dir: Path | None = None)`
  - attribute `last_outcome: dict | None` — after each `run()` it is a dict with keys `exit_code: int`, `wall_time: float`, `timed_out: bool`, `log_path: str | None`.
  - attribute `label: str` — settable by the CLI before each run; used in the log filename. Defaults to `""`.
  - method `run(self, task: str, workspace: Path) -> None` (satisfies the `HarnessDriver` Protocol).
  - Writes `workspace/TASK.md` containing the raw task text.
  - Placeholders substituted per argv token: `{task}` → raw task text (single arg), `{task_file}` → absolute path to `workspace/TASK.md`, `{workspace}` → absolute path to workspace.

- [ ] **Step 1: Write the failing test for task-file write + placeholder substitution**

Add to `tests/test_driver.py`:

```python
import sys
from pathlib import Path

from aigamedevbench.driver import CommandHarnessDriver


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_driver.py -k command -v`
Expected: FAIL with `ImportError`/`cannot import name 'CommandHarnessDriver'`.

- [ ] **Step 3: Implement `CommandHarnessDriver`**

Append to `src/aigamedevbench/driver.py` (keep existing imports; add new ones at top of file):

```python
import shlex
import subprocess
import time
from pathlib import Path


class CommandHarnessDriver:
    """Runs an arbitrary CLI harness inside the workspace to complete the task.

    The command template is shlex-split, then each token has placeholders
    substituted: {task} (raw task text as a single arg), {task_file} (path to
    workspace/TASK.md), {workspace} (workspace path). No shell is used, so the
    task text can contain any characters without injection risk.
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
        argv = []
        for token in shlex.split(self.cmd_template):
            for ph, val in repl.items():
                token = token.replace(ph, val)
            argv.append(token)
        return argv

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
        task_file = workspace / "TASK.md"
        task_file.write_text(task, encoding="utf-8")
        argv = self._build_argv(task, task_file, workspace)
        log_path = self._log_path(workspace)

        start = time.perf_counter()
        exit_code = 0
        timed_out = False
        stdout = stderr = ""
        try:
            proc = subprocess.run(
                argv, cwd=str(workspace), timeout=self.timeout,
                capture_output=True, text=True,
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_driver.py -k command -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/aigamedevbench/driver.py tests/test_driver.py
git commit -m "feat: CommandHarnessDriver core — write task, substitute placeholders, run harness"
```

---

### Task 2: `CommandHarnessDriver` failure modes + outcome metadata

**Files:**
- Modify: `src/aigamedevbench/driver.py` (no code change expected — Task 1 already implements this; this task adds the tests that lock the behavior in)
- Test: `tests/test_driver.py` (append tests)

**Interfaces:**
- Consumes: `CommandHarnessDriver` from Task 1, including `last_outcome` keys `exit_code`/`wall_time`/`timed_out`/`log_path`.
- Produces: regression coverage for timeout, missing binary, non-zero exit, change detection, and injection safety. No new public interface.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_driver.py`:

```python
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
    drv.run(f"; rm -rf {canary}", ws)
    assert canary.read_text(encoding="utf-8") == "alive"
    # And the malicious string arrives intact as one argv element.
    assert out.read_text(encoding="utf-8").splitlines() == [f"; rm -rf {canary}"]
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_driver.py -k command -v`
Expected: PASS for all `command` tests. If any fail, fix `driver.py` from Task 1 to satisfy them (do not weaken the no-raise / no-shell guarantees).

- [ ] **Step 3: Run the full driver test file**

Run: `pytest tests/test_driver.py -v`
Expected: PASS (existing NoOp/Patch tests + all command tests).

- [ ] **Step 4: Commit**

```bash
git add tests/test_driver.py src/aigamedevbench/driver.py
git commit -m "test: CommandHarnessDriver failure modes, change detection, injection safety"
```

---

### Task 3: CLI `command` driver + JSON report

**Files:**
- Modify: `src/aigamedevbench/cli.py:31-72` (the `run_cmd` function and its decorators)
- Test: `tests/test_cli.py` (append a test)

**Interfaces:**
- Consumes: `CommandHarnessDriver(cmd_template, timeout, log_dir)` with attributes `label` and `last_outcome` (Task 1); `run_testcase(...)` returning a `RunResult` with `.score`, `.id`-less but `.to_dict()` containing `testcase_id`/`category`/`score`/`status` fields, and the testcase `tc.id`.
- Produces: CLI options `--driver command`, `--harness-cmd`, `--timeout`, `--log-dir`, `--report`. When `--report PATH` is given, writes a JSON file:
  ```json
  {"harness": "...", "count": N, "mean_score": F,
   "testcases": [{<RunResult.to_dict()>, "wall_time": F,
                  "exit_code": I, "timed_out": B, "log_path": "..."}]}
  ```

- [ ] **Step 1: Write the failing CLI test**

Append to `tests/test_cli.py`:

```python
import sys


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
    assert "wall_time" in tc0 and "exit_code" in tc0 and "log_path" in tc0
    assert tc0["exit_code"] == 0


def test_run_command_driver_requires_cmd(tmp_path, monkeypatch):
    repo, tcs = _repo_and_testcases(tmp_path)
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(main, [
        "run", "--testcases-dir", str(tcs), "--driver", "command",
    ])
    assert result.exit_code == 0
    assert "harness-cmd" in result.output.lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_cli.py -k command -v`
Expected: FAIL — `command` is not a valid `--driver` choice yet (Click usage error, exit code 2).

- [ ] **Step 3: Update `run_cmd` in `cli.py`**

Replace the decorators and body of `run_cmd` (currently `src/aigamedevbench/cli.py:31-72`) with:

```python
@main.command("run")
@click.option("--testcases-dir", required=True, type=click.Path(exists=True))
@click.option("--testcase", "testcase_id", default=None, help="Run only this testcase id")
@click.option("--harness", "harness_id", default="manual", help="Harness id label")
@click.option("--driver", type=click.Choice(["noop", "patch", "command"]), default="noop")
@click.option("--patch", "patch_file", default=None, type=click.Path(exists=True))
@click.option("--harness-cmd", "harness_cmd", default=None,
              help="Command template for --driver command, e.g. 'claude -p {task}'")
@click.option("--timeout", default=600.0, type=float, help="Per-testcase harness timeout (s)")
@click.option("--log-dir", "log_dir", default="harness-logs", type=click.Path(),
              help="Where to write harness stdout/stderr logs")
@click.option("--report", "report_file", default=None, type=click.Path(),
              help="Write a JSON report to this path")
@click.option("--godot-binary", default="godot", help="Godot executable for L0/runtime verifiers")
def run_cmd(testcases_dir: str, testcase_id: str | None, harness_id: str,
            driver: str, patch_file: str | None, harness_cmd: str | None,
            timeout: float, log_dir: str, report_file: str | None,
            godot_binary: str):
    """Run testcases against a harness driver (executed inside the target game repo)."""
    from aigamedevbench.testcase import discover_testcases
    from aigamedevbench.runner import run_testcase
    from aigamedevbench.driver import NoOpDriver, PatchDriver, CommandHarnessDriver

    config = _config(godot_binary)

    if driver == "patch":
        if not patch_file:
            click.echo("--patch FILE required with --driver patch")
            return
        drv = PatchDriver(Path(patch_file).read_text(encoding="utf-8"))
    elif driver == "command":
        if not harness_cmd:
            click.echo("--harness-cmd TEMPLATE required with --driver command")
            return
        drv = CommandHarnessDriver(harness_cmd, timeout=timeout, log_dir=Path(log_dir))
    else:
        drv = NoOpDriver()

    testcases = discover_testcases(Path(testcases_dir))
    if testcase_id:
        testcases = [t for t in testcases if t.id == testcase_id]
        if not testcases:
            click.echo(f"Testcase '{testcase_id}' not found.")
            return

    needs_repo = any(t.source_kind != "folder" for t in testcases)
    repo_root = get_repo_root(Path.cwd()) if needs_repo else None

    total = 0.0
    records = []
    for tc in testcases:
        if isinstance(drv, CommandHarnessDriver):
            drv.label = tc.id
        result = run_testcase(repo_root, tc, drv, harness_id, config)
        total += result.score
        click.echo(f"{tc.id}\t{tc.category}\t{result.verifier_result.status}\t{result.score:.2f}")
        record = result.to_dict()
        if isinstance(drv, CommandHarnessDriver) and drv.last_outcome:
            record.update(drv.last_outcome)
        records.append(record)

    mean = total / len(testcases) if testcases else 0.0
    if testcases:
        click.echo(f"--- mean score: {mean:.3f} over {len(testcases)} testcase(s)")

    if report_file:
        import json
        report = {"harness": harness_id, "count": len(testcases),
                  "mean_score": mean, "testcases": records}
        Path(report_file).write_text(json.dumps(report, indent=2), encoding="utf-8")
        click.echo(f"--- report written to {report_file}")
```

Add the import at the top of `cli.py` if not already present: `from aigamedevbench.git_ops import get_repo_root` already exists — no new top-level import needed.

- [ ] **Step 4: Run the CLI tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (existing `test_list`/`test_run_noop_fails` + both new command tests).

- [ ] **Step 5: Commit**

```bash
git add src/aigamedevbench/cli.py tests/test_cli.py
git commit -m "feat: CLI --driver command with timeout, logs, and JSON report"
```

---

### Task 4: Document the harness driver in README

**Files:**
- Modify: `README.md` (the "Evaluating a real AI harness" section, around lines 63-69)

**Interfaces:**
- Consumes: the `--driver command` CLI from Task 3.
- Produces: user-facing docs. No code.

- [ ] **Step 1: Replace the "Evaluating a real AI harness" section**

In `README.md`, replace the section that currently reads (lines ~63-69):

```markdown
## Evaluating a real AI harness

Until a native harness driver lands, the loop is:

1. Have the AI complete the testcase `task` starting from `baseline_ref`.
2. Capture its change: `git diff > ai.diff`.
3. Score it: `aigdbench run --driver patch --patch ai.diff`.
```

with:

```markdown
## Evaluating a real AI harness

Use `--driver command` to run any CLI harness automatically. The driver writes
the testcase `task` to `workspace/TASK.md`, substitutes placeholders into your
command template, runs it inside the isolated workspace, and scores whatever it
changed. Placeholders: `{task}` (the task text as one argument), `{task_file}`
(path to `TASK.md`), `{workspace}` (the workspace dir).

```bash
aigdbench run --testcases-dir ./testcases \
  --driver command \
  --harness-cmd 'claude -p {task}' \
  --harness my-claude-code \
  --timeout 900 \
  --godot-binary /path/to/godot \
  --log-dir ./harness-logs \
  --report ./report.json
```

The harness's stdout/stderr go to `--log-dir`; `--report` writes a JSON summary
(per-testcase score, status, wall_time, exit_code, log path, and overall mean).
A harness that times out, errors, or exits non-zero scores that testcase 0 and
the batch continues.

The manual loop still works if you prefer it: complete the task by hand, capture
`git diff > ai.diff`, and score with `aigdbench run --driver patch --patch ai.diff`.
```

- [ ] **Step 2: Verify the full test suite still passes**

Run: `pytest`
Expected: PASS (all tests green).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document --driver command for evaluating AI harnesses"
```

---

## Self-Review

**Spec coverage:**
- CommandHarnessDriver class, `{task}`/`{task_file}`/`{workspace}` placeholders, token-level no-shell substitution → Task 1.
- `last_outcome` with exit_code/wall_time/timed_out/log_path → Task 1, asserted Task 2.
- TASK.md write → Task 1. Log capture → Task 1.
- Timeout kill, missing binary, non-zero exit, never-raise → Task 2.
- Injection regression → Task 2.
- Change detection through git status → Task 2.
- CLI `--driver command`, `--harness-cmd`, `--timeout`, `--log-dir`, `--report` → Task 3.
- JSON report shape (harness/count/mean_score/testcases[] with wall_time/exit_code/log_path) → Task 3, asserted in test.
- Terminal table unchanged + additive report → Task 3.
- Protocol/RunResult/runner/verifiers untouched → no task modifies them (constraint honored).
- README docs → Task 4.

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to" — all code shown in full.

**Type consistency:** `cmd_template: str`, `timeout: float`, `log_dir: Path | None`, `label: str`, `last_outcome: dict | None` with keys `exit_code`/`wall_time`/`timed_out`/`log_path` used identically in Task 1 (definition), Task 2 (assertions), and Task 3 (CLI `record.update`). CLI option name `--harness-cmd` → param `harness_cmd` consistent. `run_testcase` signature `(repo_root, tc, drv, harness_id, config)` matches existing usage in `cli.py`.
