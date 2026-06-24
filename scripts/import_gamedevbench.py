#!/usr/bin/env python3
"""Import GameDevBench tasks into AIGameDevBench folder-type testcases.

GameDevBench tasks are self-contained Godot projects with a frozen golden
verifier (scenes/test.tscn + scripts/test.gd that prints VALIDATION_PASSED/
FAILED). This tool converts a task into an AIGameDevBench testcase directory:

    testcases/gdb-task_XXXX/
        testcase.toml          source_kind="folder", verifier=godot_scene_assert
        baseline/              the starting project (test.* / .godot / nested dup stripped)
        verifier_scene.tscn    task's test.tscn with the script path swapped to a placeholder
        verifier.gd            auto-converted from test.gd (SINGLE checkpoint fallback)
        fix.diff               baseline -> ground-truth diff, for self-test (patch -> 1.0)

The verifier.gd auto-conversion produces ONE checkpoint mirroring GameDevBench's
overall pass/fail. To get per-checkpoint partial credit, split it by hand
afterwards (see gdb-task_0002 for a worked multi-checkpoint example).

Usage:
    python scripts/import_gamedevbench.py \
        --gdb ../GameDevBench \
        --out testcases \
        --tasks task_0002 task_0003
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# GameDevBench category -> AIGameDevBench category
CATEGORY_MAP = {
    "gameplay logic": "behavior_logic",
    "user interface": "behavior_logic",
    "2d graphics & animation": "visual_audio",
    "3d graphics & animation": "visual_audio",
}

# Dirs to drop from the copied baseline.
STRIP_NAMES = {".godot"}

# Root metadata files to drop from baseline: they leak the solution / expected
# nodes to a solver, and are not part of the runnable Godot project.
STRIP_ROOT_FILES = ("task_config.json", "task_validation.md", "validation.md")


def _strip_baseline(src_task: Path, dst_baseline: Path) -> None:
    """Copy the task project, removing test files, the .godot cache, and the
    nested duplicate directory some task zips contain (task_XXXX/tasks/task_XXXX/...)."""
    task_name = src_task.name

    def ignore(dir_path, names):
        skip = set()
        for n in names:
            if n in STRIP_NAMES:
                skip.add(n)
            # nested duplicate packaging dirs
            if n in ("tasks", "tasks_gt"):
                skip.add(n)
        return skip

    shutil.copytree(src_task, dst_baseline, ignore=ignore)
    # drop the golden verifier from the starting point
    for rel in ("scripts/test.gd", "scripts/test.gd.uid",
                "scenes/test.tscn", "scenes/test.tscn.uid"):
        p = dst_baseline / rel
        if p.exists():
            p.unlink()
    # drop solution-leaking metadata files
    for name in STRIP_ROOT_FILES:
        p = dst_baseline / name
        if p.exists():
            p.unlink()


def _load_config(src_task: Path) -> dict:
    cfg = src_task / "task_config.json"
    return json.loads(cfg.read_text(encoding="utf-8"))


def _map_category(cfg: dict) -> str:
    raw = (cfg.get("category") or cfg.get("metadata", {}).get("category") or "").strip().lower()
    return CATEGORY_MAP.get(raw, "behavior_logic")


def _toml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _write_testcase_toml(out_dir: Path, task_name: str, cfg: dict) -> None:
    instruction = cfg.get("instruction", "").strip()
    meta = cfg.get("metadata", {})
    category = _map_category(cfg)
    toml = f'''[testcase]
id = "gdb-{task_name}"
category = "{category}"
source_kind = "folder"
source_repo = "GameDevBench:{task_name}"
task = """
{instruction}
"""

[verifier]
type = "godot_scene_assert"
entry = "verifier_scene.tscn"

[scoring]
mode = "checkpoints"

[provenance]
imported_from = "GameDevBench"
task_id = {cfg.get("task_id", 0)}
name = "{_toml_escape(cfg.get("name", ""))}"
tutorial_source = "{_toml_escape(meta.get("tutorial_source", ""))}"
video_id = "{_toml_escape(meta.get("video_id", ""))}"
'''
    (out_dir / "testcase.toml").write_text(toml, encoding="utf-8")


def _write_verifier_scene(src_task: Path, out_dir: Path) -> bool:
    test_tscn = src_task / "scenes" / "test.tscn"
    if not test_tscn.exists():
        print(f"  WARN: no scenes/test.tscn in {src_task.name}; skipping scene", file=sys.stderr)
        return False
    text = test_tscn.read_text(encoding="utf-8")
    # Point the script ext_resource at the injected placeholder name.
    text = text.replace("res://scripts/test.gd", "res://__VERIFIER_GD__")
    (out_dir / "verifier_scene.tscn").write_text(text, encoding="utf-8")
    return True


def _write_verifier_gd(src_task: Path, out_dir: Path) -> None:
    """Copy the golden test.gd verbatim as verifier.gd.

    The godot_scene_assert verifier accepts both per-assertion JSON and the
    GameDevBench-style VALIDATION_PASSED/FAILED marker, so the original test.gd
    runs unchanged and is scored as a single overall checkpoint. To get
    per-checkpoint partial credit, hand-edit verifier.gd to print
    {"assertions":[...]} (see gdb-task_0002 for a worked example)."""
    test_gd = src_task / "scripts" / "test.gd"
    header = (
        "# Copied verbatim from GameDevBench test.gd by import_gamedevbench.py.\n"
        "# Scored as a SINGLE overall checkpoint via its VALIDATION_PASSED/FAILED\n"
        "# marker. For per-checkpoint partial credit, rewrite the reporting tail\n"
        '# to print {"assertions":[...]} (see gdb-task_0002 for an example).\n'
    )
    (out_dir / "verifier.gd").write_text(
        header + test_gd.read_text(encoding="utf-8"), encoding="utf-8")


def _write_fix_diff(src_task: Path, gt_task: Path, out_dir: Path) -> None:
    """Diff baseline-relevant files against ground truth, as a git-apply'able patch
    rooted at the workspace (paths like a/scripts/foo.gd b/scripts/foo.gd)."""
    if not gt_task.exists():
        print(f"  WARN: no ground truth at {gt_task}; skipping fix.diff", file=sys.stderr)
        return
    baseline = out_dir / "baseline"
    diffs: list[str] = []
    for gt_file in sorted(gt_task.rglob("*")):
        if not gt_file.is_file():
            continue
        rel = gt_file.relative_to(gt_task)
        parts = set(rel.parts)
        if ".godot" in parts or "tasks" in parts or "tasks_gt" in parts:
            continue
        if rel.parts[-1] in ("test.gd", "test.gd.uid", "test.tscn", "test.tscn.uid"):
            continue
        if rel.suffix == ".uid":  # uids are environment-specific noise
            continue
        base_file = baseline / rel
        if not base_file.exists():
            continue
        a = base_file.read_text(encoding="utf-8", errors="replace")
        b = gt_file.read_text(encoding="utf-8", errors="replace")
        if a == b:
            continue
        rel_posix = rel.as_posix()
        patch = subprocess.run(
            ["git", "diff", "--no-index", "--no-color",
             f"--src-prefix=a/", f"--dst-prefix=b/",
             str(base_file), str(gt_file)],
            capture_output=True, text=True,
        ).stdout
        # Rewrite the absolute temp paths in the header to workspace-relative ones.
        patch = _normalize_patch_paths(patch, rel_posix)
        if patch.strip():
            diffs.append(patch)
    if diffs:
        (out_dir / "fix.diff").write_text("".join(diffs), encoding="utf-8")
    else:
        print(f"  WARN: empty fix.diff for {src_task.name}", file=sys.stderr)


def _normalize_patch_paths(patch: str, rel_posix: str) -> str:
    out_lines = []
    for line in patch.splitlines(keepends=True):
        if line.startswith("diff --git "):
            out_lines.append(f"diff --git a/{rel_posix} b/{rel_posix}\n")
        elif line.startswith("--- "):
            out_lines.append(f"--- a/{rel_posix}\n")
        elif line.startswith("+++ "):
            out_lines.append(f"+++ b/{rel_posix}\n")
        else:
            out_lines.append(line)
    return "".join(out_lines)


def import_task(gdb_root: Path, out_root: Path, task_name: str) -> None:
    src_task = gdb_root / "tasks" / task_name
    gt_task = gdb_root / "tasks_gt" / task_name
    if not src_task.is_dir():
        print(f"SKIP {task_name}: not found at {src_task}", file=sys.stderr)
        return
    cfg = _load_config(src_task)

    # First-batch filter: skip display/multimodal tasks (not headless-verifiable).
    if cfg.get("requires_display"):
        print(f"SKIP {task_name}: requires_display", file=sys.stderr)
        return

    out_dir = out_root / f"gdb-{task_name}"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    _strip_baseline(src_task, out_dir / "baseline")
    _write_testcase_toml(out_dir, task_name, cfg)
    _write_verifier_scene(src_task, out_dir)
    _write_verifier_gd(src_task, out_dir)
    _write_fix_diff(src_task, gt_task, out_dir)
    print(f"OK   gdb-{task_name} -> {out_dir}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gdb", required=True, type=Path, help="GameDevBench repo root")
    ap.add_argument("--out", required=True, type=Path, help="AIGameDevBench testcases dir")
    ap.add_argument("--tasks", nargs="+", required=True, help="task ids, e.g. task_0002")
    args = ap.parse_args(argv)

    gdb_root = args.gdb.resolve()
    out_root = args.out.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    for t in args.tasks:
        import_task(gdb_root, out_root, t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
