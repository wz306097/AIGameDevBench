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
survey/runner:
  git worktree add <baseline_ref>      # isolated copy of the starting state
  driver.run(task, workspace)          # noop | patch | (your AI harness)
  L0/L1 gate                           # scene loads? no broken refs? else score 0
  inject golden verifier -> score      # deleted after scoring (anti-gaming)
```

`run` must be executed **inside the target game repo** (the runner uses
`git worktree` to check out `baseline_ref`).

## Quick start (the included demo)

```bash
# 1. make a minimal game repo
mkdir -p /tmp/game/data && cd /tmp/game
git init -q && git config user.email d@d.com && git config user.name d
printf '{\n  "name": "Elite Slime",\n  "attack": 50\n}\n' > data/elite.json
git add . && git commit -qm baseline
SHA=$(git rev-parse HEAD)

# 2. point the demo testcase at that commit
#    edit testcases/bench-0001-attack-buff/testcase.toml -> baseline_ref = "$SHA"

# 3. run it (from inside /tmp/game)
TCDIR=/path/to/AIGameDevBench/testcases
aigdbench list --testcases-dir "$TCDIR"
aigdbench run  --testcases-dir "$TCDIR" --testcase bench-0001-attack-buff --driver noop
aigdbench run  --testcases-dir "$TCDIR" --testcase bench-0001-attack-buff \
  --driver patch --patch "$TCDIR/bench-0001-attack-buff/fix.diff"
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
  --report ./report.json
```

The harness's stdout/stderr go to `--log-dir`; `--report` writes a JSON summary
(per-testcase score, status, wall_time, exit_code, log path, and overall mean).
A harness that times out, errors, or exits non-zero scores that testcase 0 and
the batch continues.

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
