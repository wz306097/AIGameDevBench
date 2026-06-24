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
@click.option("--driver", type=click.Choice(["noop", "patch", "command"]), default="noop")
@click.option("--patch", "patch_file", default=None, type=click.Path(exists=True))
@click.option("--harness-cmd", "harness_cmd", default=None,
              help="Command template for --driver command, e.g. 'claude -p {task}'")
@click.option("--timeout", default=600.0, type=float, help="Per-testcase harness timeout (s)")
@click.option("--log-dir", "log_dir", default="harness-logs", type=click.Path(),
              help="Where to write harness stdout/stderr logs")
@click.option("--report", "report_file", default=None, type=click.Path(),
              help="Write a JSON report to this path")
@click.option("--godot-binary", default="godot", help="Godot executable for L0/runtime verifiers")
def run_cmd(testcases_dir: str, testcase_id: str | None, harness_id: str,
            driver: str, patch_file: str | None, harness_cmd: str | None,
            timeout: float, log_dir: str, report_file: str | None,
            godot_binary: str):
    """Run testcases against a harness driver (executed inside the target game repo)."""
    from aigamedevbench.testcase import discover_testcases
    from aigamedevbench.runner import run_testcase
    from aigamedevbench.driver import NoOpDriver, PatchDriver, CommandHarnessDriver

    config = _config(godot_binary)

    if driver == "patch":
        if not patch_file:
            click.echo("--patch FILE required with --driver patch")
            return
        drv = PatchDriver(Path(patch_file).read_text(encoding="utf-8"))
    elif driver == "command":
        if not harness_cmd:
            click.echo("--harness-cmd TEMPLATE required with --driver command")
            return
        drv = CommandHarnessDriver(harness_cmd, timeout=timeout, log_dir=Path(log_dir))
    else:
        drv = NoOpDriver()

    testcases = discover_testcases(Path(testcases_dir))
    if testcase_id:
        testcases = [t for t in testcases if t.id == testcase_id]
        if not testcases:
            click.echo(f"Testcase '{testcase_id}' not found.")
            return

    # Folder-type testcases are self-contained and run anywhere; only git-type
    # ones need a repo root. Resolve it lazily and tolerantly: if cwd isn't a
    # git repo, git-type testcases fail individually (below) rather than aborting
    # the whole batch — a non-git cwd is normal when scoring folder-type cases.
    needs_repo = any(t.source_kind != "folder" for t in testcases)
    repo_root = None
    if needs_repo:
        try:
            repo_root = get_repo_root(Path.cwd())
        except (RuntimeError, FileNotFoundError):
            repo_root = None

    total = 0.0
    records = []
    for tc in testcases:
        if isinstance(drv, CommandHarnessDriver):
            drv.label = tc.id
        try:
            result = run_testcase(repo_root, tc, drv, harness_id, config)
        except Exception as e:
            # One un-runnable testcase (e.g. a git-type case with no repo root,
            # or a bad baseline_ref) must not kill the rest of the batch.
            click.echo(f"{tc.id}\t{tc.category}\terror\t0.00\t{e}")
            records.append({"testcase_id": tc.id, "category": tc.category,
                            "score": 0.0, "status": "error", "error": str(e)})
            continue
        total += result.score
        click.echo(f"{tc.id}\t{tc.category}\t{result.verifier_result.status}\t{result.score:.2f}")
        record = result.to_dict()
        if isinstance(drv, CommandHarnessDriver) and drv.last_outcome is not None:
            record.update(drv.last_outcome)
        records.append(record)

    mean = total / len(testcases) if testcases else 0.0
    if testcases:
        click.echo(f"--- mean score: {mean:.3f} over {len(testcases)} testcase(s)")

    if report_file:
        import json
        report = {"harness": harness_id, "count": len(testcases),
                  "mean_score": mean, "testcases": records}
        Path(report_file).write_text(json.dumps(report, indent=2), encoding="utf-8")
        click.echo(f"--- report written to {report_file}")
