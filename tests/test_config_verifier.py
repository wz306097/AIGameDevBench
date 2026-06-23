from __future__ import annotations

import json
from pathlib import Path

from aigamedevbench.testcase import Testcase
from aigamedevbench.verifiers.config_verifier import ConfigVerifier


def _tc(dir: Path) -> Testcase:
    return Testcase("t", "intent_translation", "ref", "task", "py_config",
                    "verify.py", "fields", dir)


def test_literal_and_derived_pass(tmp_path):
    ws = tmp_path / "ws"
    (ws / "data").mkdir(parents=True)
    (ws / "data" / "char.json").write_text(json.dumps(
        {"crit_rate": 0.15, "attack": 60}), encoding="utf-8")
    tc_dir = tmp_path / "tc"
    tc_dir.mkdir()
    (tc_dir / "expected.json").write_text(json.dumps({"fields": [
        {"name": "crit_rate", "aliases": ["crit_rate"], "files_glob": "**/*.json",
         "expected": 0.15, "tol": 1e-6},
        {"name": "attack", "aliases": ["attack"], "files_glob": "**/*.json",
         "expected": 60, "tol": 1e-6, "base": 50, "must_differ_from_base": True},
    ]}), encoding="utf-8")
    result = ConfigVerifier().verify(_tc(tc_dir), ws)
    assert result.status == "pass"
    assert result.score == 1.0


def test_copied_base_fails_must_differ(tmp_path):
    ws = tmp_path / "ws"
    (ws / "data").mkdir(parents=True)
    (ws / "data" / "char.json").write_text(json.dumps({"attack": 50}), encoding="utf-8")
    tc_dir = tmp_path / "tc"
    tc_dir.mkdir()
    (tc_dir / "expected.json").write_text(json.dumps({"fields": [
        {"name": "attack", "aliases": ["attack"], "files_glob": "**/*.json",
         "expected": 50, "tol": 1e-6, "base": 50, "must_differ_from_base": True},
    ]}), encoding="utf-8")
    result = ConfigVerifier().verify(_tc(tc_dir), ws)
    assert result.status == "fail"


def test_alias_locates_renamed_field(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "c.json").write_text(json.dumps({"critical_chance": 0.15}), encoding="utf-8")
    tc_dir = tmp_path / "tc"
    tc_dir.mkdir()
    (tc_dir / "expected.json").write_text(json.dumps({"fields": [
        {"name": "crit", "aliases": ["crit_rate", "critical_chance"],
         "files_glob": "**/*.json", "expected": 0.15, "tol": 1e-6},
    ]}), encoding="utf-8")
    result = ConfigVerifier().verify(_tc(tc_dir), ws)
    assert result.status == "pass"
