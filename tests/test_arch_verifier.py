from __future__ import annotations

import json

from aigamedevbench.testcase import Testcase
from aigamedevbench.verifiers.arch_verifier import (
    ArchVerifier, find_res_paths, find_extends, find_imports,
)

GOOD_GD = '''extends Node

@export var save_path: String

func save():
    var f = FileAccess.open(save_path, FileAccess.WRITE)
'''

BAD_GD = '''extends Node

const UI = preload("res://ui/hud.gd")

func save():
    var f = FileAccess.open("res://saves/save.dat", FileAccess.WRITE)
'''


def test_helpers():
    assert find_extends(GOOD_GD) == "Node"
    assert find_res_paths(BAD_GD) == ["res://ui/hud.gd", "res://saves/save.dat"]
    assert "res://ui/hud.gd" in find_imports(BAD_GD)


def _setup(tmp_path, gd_text):
    tc_dir = tmp_path / "tc"; tc_dir.mkdir()
    (tc_dir / "arch_rules.json").write_text(json.dumps({
        "target_files": ["scripts/save_manager.gd"],
        "rules": [
            {"id": "no_ui_import", "type": "forbid_import_glob", "glob": "ui/", "weight": 25},
            {"id": "no_hardcoded_path", "type": "forbid_hardcoded_res_path", "weight": 15},
            {"id": "must_extend", "type": "require_extends", "base": "Node", "weight": 30},
        ],
    }), encoding="utf-8")
    ws = tmp_path / "ws"; (ws / "scripts").mkdir(parents=True)
    (ws / "scripts" / "save_manager.gd").write_text(gd_text, encoding="utf-8")
    tc = Testcase("t", "architecture", "ref", "task", "py_gdscript_ast",
                  "verify.py", "weighted", tc_dir)
    return tc, ws


def test_clean_code_scores_full(tmp_path):
    tc, ws = _setup(tmp_path, GOOD_GD)
    result = ArchVerifier().verify(tc, ws)
    assert result.score == 1.0
    assert result.status == "pass"


def test_violations_reduce_score(tmp_path):
    tc, ws = _setup(tmp_path, BAD_GD)
    result = ArchVerifier().verify(tc, ws)
    assert abs(result.score - 0.6) < 1e-9
    assert result.status == "partial"
