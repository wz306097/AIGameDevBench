from __future__ import annotations

from aigamedevbench.driver import NoOpDriver, PatchDriver


def test_noop_changes_nothing(tmp_path):
    (tmp_path / "f.txt").write_text("a\n", encoding="utf-8")
    NoOpDriver().run("task", tmp_path)
    assert (tmp_path / "f.txt").read_text(encoding="utf-8") == "a\n"


def test_patch_driver_applies(tmp_path):
    from aigamedevbench.git_ops import git_run
    git_run(["init"], cwd=tmp_path)
    git_run(["config", "user.email", "t@t.com"], cwd=tmp_path)
    git_run(["config", "user.name", "t"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("a\n", encoding="utf-8")
    git_run(["add", "f.txt"], cwd=tmp_path)
    git_run(["commit", "-m", "i"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("b\n", encoding="utf-8")
    patch = git_run(["diff"], cwd=tmp_path)
    git_run(["checkout", "f.txt"], cwd=tmp_path)
    PatchDriver(patch).run("task", tmp_path)
    assert (tmp_path / "f.txt").read_text(encoding="utf-8") == "b\n"
