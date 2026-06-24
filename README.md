# AIGameDevBench

A SWE-bench-style **controlled benchmark** for evaluating how well AI coding
harnesses do **Godot game development**.

Each testcase = (source game repo @ a baseline commit) + (a task) + (a frozen
golden verifier). A harness's change is scored by an automated verifier. The
contract: **doing nothing must score 0; the correct change scores 1.**

## Install

```bash
git clone https://github.com/wz306097/AIGameDevBench.git
cd AIGameDevBench
python -m pip install -e ".[dev]"
```

Python ≥ 3.10. The pure-Python verifiers need no Godot. The runtime verifiers
(`godot_scenetree` / `visual_static` / `interaction_routing`) need a `godot`
binary on PATH (pass `--godot-binary` to point elsewhere).

## How a benchmark run works

```
runner:
  prepare isolated workspace            # see "starting state" below
  driver.run(task, workspace)           # noop | patch | (your AI harness)
  godot --import (folder-type)          # build the resource cache so scenes load
  L0/L1 gate                            # scene loads? no broken refs? else score 0
  inject golden verifier -> score       # deleted after scoring (anti-gaming)
```

Two starting-state shapes, set per testcase by `source_kind`:

| `source_kind` | starting state | where you run it |
|---|---|---|
| `folder` (the imported `gdb-task_*`) | the testcase's self-contained `baseline/` dir, copied to a temp dir + `git init` | **any directory** |
| `git` | a commit in the source game repo, checked out via `git worktree` | **inside that game repo** |

So folder-type testcases are self-contained and run anywhere; only git-type
testcases must be run from inside their target game repo.

## Quick start (a self-contained testcase)

`gdb-task_0002` is a folder-type testcase, so it runs from anywhere with no
setup. It needs `godot` on PATH (it boots a scene to score).

```bash
TCDIR=/path/to/AIGameDevBench/testcases

aigdbench list --testcases-dir "$TCDIR"

# baseline check: doing nothing must score 0
aigdbench run --testcases-dir "$TCDIR" --testcase gdb-task_0002 --driver noop

# replay the known-good fix: must score 1
aigdbench run --testcases-dir "$TCDIR" --testcase gdb-task_0002 \
  --driver patch --patch "$TCDIR/gdb-task_0002/fix.diff"
```

Expected:

| driver | status | score |
|---|---|---|
| noop | fail | 0.00 |
| patch (fix.diff) | pass | 1.00 |

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
  --workspace-root ./bench-workspaces \
  --report ./report.json
```

The harness's stdout/stderr go to `--log-dir`; `--report` writes a JSON summary
(per-testcase score, status, wall_time, exit_code, log path, and overall mean).
A harness that times out, errors, or exits non-zero scores that testcase 0 and
the batch continues — and its log tail is printed to the screen immediately, so
failures are visible without opening the log file.

**`--workspace-root`:** by default each testcase's workspace is created under the
OS temp dir. Some harnesses gate file edits under temp paths behind a manual
approval prompt, which silently hangs an unattended run. Point `--workspace-root`
at a directory your harness trusts (e.g. one inside your project) to avoid this.

The manual loop still works if you prefer it: complete the task by hand, capture
`git diff > ai.diff`, and score with `aigdbench run --driver patch --patch ai.diff`.

## Testcase format

See [`testcases/README.md`](testcases/README.md) for the manifest schema, the
five capability categories, and all six verifier types.

## Verifier types

| type | needs Godot | reads | what it checks |
|---|---|---|---|
| `py_config` | no | `expected.json` | numeric/config fields by alias; anti-copy guard |
| `py_tscn_diff` | no | `expected_delta.json` + `baseline/` | scene node/prop delta, side-effect free |
| `py_gdscript_ast` | no | `arch_rules.json` | import/extends/path constraints, weighted |
| `godot_scenetree` | yes | `verifier.gd` | runtime assertions via headless SceneTree |
| `visual_static` | yes | `verifier.gd` | structured layout assertions |
| `interaction_routing` | yes | `verifier.gd` | click routing / focus order |

## Tests

```bash
pytest
```
