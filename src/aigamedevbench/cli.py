from __future__ import annotations

from pathlib import Path

import click

from aigamedevbench.git_ops import get_repo_root


def _config(godot_binary: str) -> dict:
    return {"global": {"godot": {"binary": godot_binary}}}


@click.group()
@click.version_option()
def main():
    """AIGameDevBench: controlled benchmark for AI Godot game development."""
    pass


@main.command("list")
@click.option("--testcases-dir", required=True, type=click.Path(exists=True))
def list_cmd(testcases_dir: str):
    """List discovered testcases."""
    from aigamedevbench.testcase import discover_testcases

    for tc in discover_testcases(Path(testcases_dir)):
        click.echo(f"{tc.id}\t{tc.category}\t{tc.verifier_type}")


@main.command("run")
@click.option("--testcases-dir", required=True, type=click.Path(exists=True))
@click.option("--testcase", "testcase_id", default=None, help="Run only this testcase id")
@click.option("--harness", "harness_id", default="manual", help="Harness id label")
@click.option("--driver", type=click.Choice(["noop", "patch"]), default="noop")
@click.option("--patch", "patch_file", default=None, type=click.Path(exists=True))
@click.option("--godot-binary", default="godot", help="Godot executable for L0/runtime verifiers")
def run_cmd(testcases_dir: str, testcase_id: str | None, harness_id: str,
            driver: str, patch_file: str | None, godot_binary: str):
    """Run testcases against a harness driver (executed inside the target game repo)."""
    from aigamedevbench.testcase import discover_testcases
    from aigamedevbench.runner import run_testcase
    from aigamedevbench.driver import NoOpDriver, PatchDriver

    repo_root = get_repo_root(Path.cwd())
    config = _config(godot_binary)

    if driver == "patch":
        if not patch_file:
            click.echo("--patch FILE required with --driver patch")
            return
        drv = PatchDriver(Path(patch_file).read_text(encoding="utf-8"))
    else:
        drv = NoOpDriver()

    testcases = discover_testcases(Path(testcases_dir))
    if testcase_id:
        testcases = [t for t in testcases if t.id == testcase_id]
        if not testcases:
            click.echo(f"Testcase '{testcase_id}' not found.")
            return

    total = 0.0
    for tc in testcases:
        result = run_testcase(repo_root, tc, drv, harness_id, config)
        total += result.score
        click.echo(f"{tc.id}\t{tc.category}\t{result.verifier_result.status}\t{result.score:.2f}")
    if testcases:
        click.echo(f"--- mean score: {total / len(testcases):.3f} over {len(testcases)} testcase(s)")
