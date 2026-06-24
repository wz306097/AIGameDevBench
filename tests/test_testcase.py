from __future__ import annotations

import pytest

from aigamedevbench.testcase import load_testcase, discover_testcases


def _write(dir, toml_text):
    dir.mkdir(parents=True, exist_ok=True)
    (dir / "testcase.toml").write_text(toml_text, encoding="utf-8")


def test_load_minimal(tmp_path):
    _write(tmp_path / "bench-0001", """
[testcase]
id = "bench-0001"
category = "behavior_logic"
baseline_ref = "abc123"
task = "Enemy patrols A to B"

[verifier]
type = "godot_scenetree"
entry = "verifier.gd"

[scoring]
mode = "checkpoints"
""")
    tc = load_testcase(tmp_path / "bench-0001")
    assert tc.id == "bench-0001"
    assert tc.category == "behavior_logic"
    assert tc.baseline_ref == "abc123"
    assert tc.verifier_type == "godot_scenetree"
    assert tc.verifier_entry == "verifier.gd"
    assert tc.scoring_mode == "checkpoints"
    assert tc.source_repo is None


def test_load_with_provenance(tmp_path):
    _write(tmp_path / "bench-0002", """
[testcase]
id = "bench-0002"
category = "precise_edit"
baseline_ref = "p1"
task = "Add Timer"
source_repo = "game-a"

[verifier]
type = "py_tscn_diff"
entry = "verify.py"

[scoring]
mode = "tristate"

[provenance]
source_session = "2026-06-03-002"
error_commit = "errc"
fix_commit = "fixc"
""")
    tc = load_testcase(tmp_path / "bench-0002")
    assert tc.source_repo == "game-a"
    assert tc.provenance["error_commit"] == "errc"
    assert tc.provenance["fix_commit"] == "fixc"


def test_source_kind_defaults_to_git(tmp_path):
    _write(tmp_path / "bench-git", """
[testcase]
id = "bench-git"
category = "behavior_logic"
baseline_ref = "abc123"
task = "t"

[verifier]
type = "godot_scenetree"
entry = "v.gd"

[scoring]
mode = "checkpoints"
""")
    tc = load_testcase(tmp_path / "bench-git")
    assert tc.source_kind == "git"


def test_folder_source_kind_without_baseline_ref(tmp_path):
    _write(tmp_path / "gdb-task_0002", """
[testcase]
id = "gdb-task_0002"
category = "behavior_logic"
source_kind = "folder"
task = "Make the projectile advance the quest"

[verifier]
type = "godot_scene_assert"
entry = "verifier_scene.tscn"

[scoring]
mode = "checkpoints"
""")
    tc = load_testcase(tmp_path / "gdb-task_0002")
    assert tc.source_kind == "folder"
    assert tc.baseline_ref == ""
    assert tc.verifier_type == "godot_scene_assert"


def test_invalid_source_kind_rejected(tmp_path):
    _write(tmp_path / "bad-src", """
[testcase]
id = "bad-src"
category = "behavior_logic"
source_kind = "svn"
task = "t"

[verifier]
type = "godot_scene_assert"
entry = "v.tscn"

[scoring]
mode = "checkpoints"
""")
    with pytest.raises(ValueError, match="source_kind"):
        load_testcase(tmp_path / "bad-src")


def test_invalid_category_rejected(tmp_path):
    _write(tmp_path / "bad", """
[testcase]
id = "bad"
category = "nonsense"
baseline_ref = "x"
task = "t"

[verifier]
type = "godot_scenetree"
entry = "v.gd"

[scoring]
mode = "checkpoints"
""")
    with pytest.raises(ValueError, match="category"):
        load_testcase(tmp_path / "bad")


def test_discover(tmp_path):
    for i in (1, 2):
        _write(tmp_path / f"bench-000{i}", f"""
[testcase]
id = "bench-000{i}"
category = "behavior_logic"
baseline_ref = "r"
task = "t"

[verifier]
type = "godot_scenetree"
entry = "v.gd"

[scoring]
mode = "checkpoints"
""")
    (tmp_path / "not-a-testcase").mkdir()
    found = discover_testcases(tmp_path)
    assert {t.id for t in found} == {"bench-0001", "bench-0002"}
