from __future__ import annotations

import json

from aigamedevbench.testcase import Testcase
from aigamedevbench.verifiers.tscn_diff_verifier import TscnDiffVerifier

BASE = """[gd_scene load_steps=2 format=3 uid="uid://a"]

[node name="Player" type="CharacterBody2D"]
"""

GOOD = BASE + """
[node name="Cooldown" type="Timer" parent="Player"]
wait_time = 0.5
"""

SIDE_EFFECT = GOOD + """
[node name="Extra" type="Node2D" parent="Player"]
"""


def _setup(tmp_path, after_text):
    tc_dir = tmp_path / "tc"; tc_dir.mkdir()
    (tc_dir / "baseline").mkdir()
    (tc_dir / "baseline" / "player.tscn").write_text(BASE, encoding="utf-8")
    (tc_dir / "expected_delta.json").write_text(json.dumps({
        "scene": "scenes/player.tscn",
        "baseline_scene": "baseline/player.tscn",
        "expected": {"added_nodes": ["Player/Cooldown"],
                     "removed_nodes": [], "changed_props": {}},
    }), encoding="utf-8")
    ws = tmp_path / "ws"; (ws / "scenes").mkdir(parents=True)
    (ws / "scenes" / "player.tscn").write_text(after_text, encoding="utf-8")
    tc = Testcase("t", "precise_edit", "ref", "task", "py_tscn_diff",
                  "verify.py", "tristate", tc_dir)
    return tc, ws


def test_correct_change_passes(tmp_path):
    tc, ws = _setup(tmp_path, GOOD)
    result = TscnDiffVerifier().verify(tc, ws)
    assert result.status == "pass"


def test_side_effect_is_partial(tmp_path):
    tc, ws = _setup(tmp_path, SIDE_EFFECT)
    result = TscnDiffVerifier().verify(tc, ws)
    assert result.status == "partial"


def test_missing_change_fails(tmp_path):
    tc, ws = _setup(tmp_path, BASE)
    result = TscnDiffVerifier().verify(tc, ws)
    assert result.status == "fail"
