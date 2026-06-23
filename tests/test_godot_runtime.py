from __future__ import annotations

import shutil

import pytest

from aigamedevbench.testcase import Testcase
from aigamedevbench.verifiers.godot_runtime import (
    GodotSceneTreeVerifier, parse_assertion_json,
)


def test_parse_assertion_json():
    out = 'noise\n{"assertions": [{"name": "moved", "pass": true}, {"name": "ranged", "pass": false}]}\ntail'
    checks = parse_assertion_json(out)
    assert len(checks) == 2
    assert checks[0].name == "moved" and checks[0].passed is True
    assert checks[1].passed is False


def test_missing_binary_is_error(tmp_path, monkeypatch):
    monkeypatch.setattr("aigamedevbench.verifiers.godot_runtime.shutil.which",
                        lambda _: None)
    tc_dir = tmp_path / "tc"; tc_dir.mkdir()
    (tc_dir / "verifier.gd").write_text("extends SceneTree\n", encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()
    tc = Testcase("t", "behavior_logic", "ref", "task", "godot_scenetree",
                  "verifier.gd", "checkpoints", tc_dir)
    result = GodotSceneTreeVerifier().verify(tc, ws)
    assert result.status == "error"


@pytest.mark.skipif(shutil.which("godot") is None, reason="godot not installed")
def test_real_godot_runs(tmp_path):
    tc_dir = tmp_path / "tc"; tc_dir.mkdir()
    (tc_dir / "verifier.gd").write_text(
        'extends SceneTree\n'
        'func _initialize():\n'
        '    print(JSON.stringify({"assertions": [{"name": "ok", "pass": true}]}))\n'
        '    quit()\n',
        encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    tc = Testcase("t", "behavior_logic", "ref", "task", "godot_scenetree",
                  "verifier.gd", "checkpoints", tc_dir)
    result = GodotSceneTreeVerifier().verify(tc, ws)
    assert result.status == "pass"


def test_interaction_routing_registered():
    from aigamedevbench.verifiers.base import get_verifier
    from aigamedevbench.verifiers import godot_runtime  # noqa: F401
    v = get_verifier("interaction_routing")
    assert v is not None
