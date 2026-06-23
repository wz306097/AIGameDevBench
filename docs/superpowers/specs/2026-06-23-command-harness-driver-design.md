# Command Harness Driver — Design

## Goal

Let AIGameDevBench run a real AI coding harness automatically against
testcases, instead of the current offline loop (run the AI by hand, capture
`git diff`, score with `--driver patch`).

A new driver invokes an arbitrary CLI harness inside the isolated workspace,
passes the testcase `task` to it, and lets the existing runner detect the
harness's file changes and score them with the frozen golden verifier.

## Contract (unchanged)

The existing benchmark contract holds: doing nothing scores 0, the correct
change scores 1. The new driver only changes *how* the workspace gets mutated;
change-detection (`git status`), the L0/L1 gate, and verifier scoring are
untouched.

## Architecture

Main chain is unchanged:

```
CLI builds driver
  -> run_testcase(repo_root, tc, driver, harness_id, config)
       -> driver.run(task, workspace)        # NEW driver does the work here
       -> git status detects changed files
       -> L0/L1 gate
       -> inject golden verifier -> score
  -> RunResult
```

Only `driver.py` and `cli.py` change. `runner.py`, `RunResult`, the
`HarnessDriver` Protocol, and the verifiers are all left as-is.

## Component: `CommandHarnessDriver` (`src/aigamedevbench/driver.py`)

```
CommandHarnessDriver(cmd_template: str, timeout: float, log_dir: Path)
    last_outcome: dict | None   # populated after each run()

    run(task, workspace) -> None:
        1. Write `task` to workspace/TASK.md (always, so {task_file} works).
        2. tokens = shlex.split(cmd_template)
        3. For each token, substitute placeholders by exact whole-token or
           in-token replacement:
              {task}      -> the raw task text (stays ONE arg even with
                             spaces/newlines/';' — no shell, no injection)
              {task_file} -> absolute path to workspace/TASK.md
              {workspace} -> absolute path to workspace
        4. subprocess.run(tokens, cwd=workspace, timeout=timeout,
                          capture_output=True, text=True)   # shell=False
        5. Write stdout+stderr+exit code to log_dir/<seq>-<safe-label>.log
        6. Record self.last_outcome = {
              exit_code, wall_time, timed_out, log_path
           }
           Never raise: FileNotFoundError -> exit_code=-1; TimeoutExpired ->
           timed_out=True, kill process. Driver always returns normally.
```

Design notes:

- **Placeholder substitution is token-level**, performed AFTER `shlex.split`,
  so a `{task}` containing spaces, newlines, or shell metacharacters is always
  delivered as a single argv element. The command never goes through a shell,
  so there is no command-injection surface. This is why `{task}` (inline single
  arg) and `{task_file}` (path) are both safe.
- **Both placeholders are always available.** Default usage is `{task}`;
  `{task_file}` is provided for tools that prefer reading a prompt file.
- **`last_outcome`** is an instance attribute. The CLI runs testcases
  sequentially and reads `last_outcome` immediately after each
  `run_testcase`, associating it with the current testcase id. No Protocol
  change is needed to surface execution metadata.
- **No wall-clock in filenames.** Log file names use an internal incrementing
  counter plus a sanitized label (passed from CLI as the testcase id via a
  settable attribute, or the counter alone). `wall_time` uses
  `time.perf_counter()` deltas (relative duration), avoiding absolute-clock
  dependence.

Existing `NoOpDriver` and `PatchDriver` are unchanged.

## Component: CLI (`src/aigamedevbench/cli.py`)

`run` command gains:

- `--driver command` (added to the existing `Choice`)
- `--harness-cmd TEXT` command template, e.g.
  `--harness-cmd 'claude -p {task}'` or `--harness-cmd 'mytool --file {task_file}'`
- `--timeout FLOAT` seconds (default 600)
- `--log-dir PATH` (default `./harness-logs`)
- `--report PATH` optional JSON report output

Run loop, per testcase:

1. Set the driver's current label to `tc.id` (for the log filename).
2. `result = run_testcase(...)` as today; print the existing terminal row.
3. Build a report record: `result.to_dict()` merged with
   `drv.last_outcome` (`wall_time`, `exit_code`, `timed_out`, `log_path`).

After the loop, if `--report` is set, write:

```json
{
  "harness": "<harness id>",
  "count": <n>,
  "mean_score": <float>,
  "testcases": [ { ...RunResult.to_dict(), "wall_time", "exit_code",
                   "timed_out", "log_path" }, ... ]
}
```

Terminal table output is unchanged; the JSON report is additive.

## Error handling boundaries

- harness binary missing -> `FileNotFoundError` caught, `exit_code=-1`, run
  continues to next testcase.
- timeout -> process killed, `timed_out=True`, testcase scores 0, run
  continues.
- any other exception inside `run()` is caught and logged; it never propagates
  to the batch loop. A failing harness on one testcase never aborts the batch.

In all failure modes the workspace simply ends up unchanged (or partially
changed), and the existing L0/L1 gate + verifier assign the score — usually 0.

## Testing (TDD)

`tests/test_driver.py` (new):

- task text is written to `workspace/TASK.md`.
- `{task}` substitution keeps multi-word / multi-line task as a single argv
  element (use a fake harness like `python -c` that echoes its argv to a file).
- `{task_file}` substitutes the TASK.md path; `{workspace}` substitutes the dir.
- a fake harness that writes a file produces a detected change.
- timeout: a sleeping fake harness is killed; `timed_out=True`, no raise.
- non-zero exit: driver records `exit_code` and does not raise.
- `last_outcome` has all four fields after a run.
- injection regression: task containing `; rm -rf {workspace}` does NOT execute
  — the file the malicious string would delete still exists afterward.

`tests/test_cli.py` (extend) or `tests/test_runner.py`:

- run a folder-type testcase with a fake harness via `--driver command`,
  assert the JSON report structure: `harness`, `count`, `mean_score`,
  per-testcase `score`/`status`/`wall_time`/`exit_code`/`log_path`.

## Out of scope (YAGNI)

- No change to the `HarnessDriver` Protocol or `RunResult` dataclass.
- No parallel/concurrent testcase execution.
- No HTTP/API driver, no in-process Python-callable driver.
- No retry logic.

## Example usage

```bash
# sanity: baseline scores 0
aigdbench run --testcases-dir ./testcases --driver noop

# real harness over all testcases, JSON report
aigdbench run --testcases-dir ./testcases \
  --driver command \
  --harness-cmd 'claude -p {task}' \
  --harness my-claude-code \
  --timeout 900 \
  --godot-binary /path/to/godot \
  --log-dir ./harness-logs \
  --report ./report.json
```
