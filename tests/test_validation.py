from __future__ import annotations

from pathlib import Path

from aigamedevbench import validation
from aigamedevbench.validation import check_gd_syntax, run_validation


def test_paren_in_string_not_counted(tmp_path):
    # Regression: a '(' inside a string literal must not be read as an unclosed
    # paren. GameDevBench's vendored QuestManager.gd has `split("(")[0]`.
    (tmp_path / "a.gd").write_text(
        'extends Node\n'
        'func f():\n'
        '\tvar callable = function.split("(")[0]\n',
        encoding="utf-8")
    issues = check_gd_syntax(tmp_path, ["a.gd"])
    assert issues == []


def test_paren_in_comment_not_counted(tmp_path):
    (tmp_path / "a.gd").write_text(
        'extends Node\n'
        '# get only function name without ()\n'
        'func f():\n'
        '\tpass\n',
        encoding="utf-8")
    assert check_gd_syntax(tmp_path, ["a.gd"]) == []


def test_real_unclosed_paren_still_flagged(tmp_path):
    (tmp_path / "a.gd").write_text(
        'extends Node\n'
        'func f():\n'
        '\tvar x = foo(1, 2\n',
        encoding="utf-8")
    issues = check_gd_syntax(tmp_path, ["a.gd"])
    assert any("unclosed" in i for i in issues)


def test_real_unmatched_close_paren_still_flagged(tmp_path):
    (tmp_path / "a.gd").write_text(
        'extends Node\n'
        'func f():\n'
        '\tvar x = 1)\n',
        encoding="utf-8")
    issues = check_gd_syntax(tmp_path, ["a.gd"])
    assert any("unmatched" in i for i in issues)


def test_escaped_quote_in_string(tmp_path):
    # A backslash-escaped quote must not end the string early, which would
    # otherwise expose a '(' that is really inside the string.
    (tmp_path / "a.gd").write_text(
        'extends Node\n'
        'func f():\n'
        '\tvar s = "a \\" ( b"\n',
        encoding="utf-8")
    assert check_gd_syntax(tmp_path, ["a.gd"]) == []


def test_run_validation_calls_godot_import_before_l0(tmp_path, monkeypatch):
    # The import pass must run before L0 boots changed scenes so imported
    # resources resolve. Assert godot_import is invoked, ahead of run_l0.
    calls = []
    monkeypatch.setattr(validation, "godot_import",
                        lambda root, binary="godot": calls.append("import"))
    monkeypatch.setattr(validation, "run_l0",
                        lambda root, scenes, binary="godot": (calls.append("l0"), (True, []))[1])
    monkeypatch.setattr(validation, "run_l1",
                        lambda root, changed: (True, []))
    result = run_validation(tmp_path, ["scenes/x.tscn"], {})
    assert calls == ["import", "l0"]
    assert result.l0_pass and result.l1_pass


def test_godot_import_noop_without_binary(tmp_path, monkeypatch):
    # No godot on PATH -> import is a silent no-op, never raises.
    monkeypatch.setattr(validation.shutil, "which", lambda _: None)
    validation.godot_import(tmp_path)  # must not raise
