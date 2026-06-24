from __future__ import annotations

from pathlib import Path

import click

from aigamedevbench.git_ops import get_repo_root


def _config(godot_binary: str) -> dict:
    return {"global": {"godot": {"binary": godot_binary}}}


def _echo_harness_failure(testcase_id: str, outcome: dict, tail_lines: int = 30) -> None:
    """Print a harness failure (timeout, stall, approval-block, or non-zero exit)
    and its log tail to the screen so problems are visible immediately instead of
    buried in a log file."""
    timed_out = outcome.get("timed_out")
    stalled = outcome.get("stalled")
    blocked = outcome.get("blocked_on_approval")
    exit_code = outcome.get("exit_code", 0)
    if not (timed_out or stalled or blocked) and exit_code == 0:
        return
    if blocked:
        reason = "BLOCKED ON APPROVAL"
    elif stalled:
        reason = "STALLED (no output)"
    elif timed_out:
        reason = "TIMEOUT"
    else:
        reason = f"exit_code={exit_code}"
    click.echo(f"  !! harness {reason} for {testcase_id}", err=True)
    log_path = outcome.get("log_path")
    if not log_path:
        click.echo("     (no log captured - run with --log-dir to capture output)", err=True)
        return
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        click.echo(f"     (could not read log {log_path}: {e})", err=True)
        return
    lines = text.splitlines()
    click.echo(f"     log: {log_path}", err=True)
    for line in lines[-tail_lines:]:
        click.echo(f"     | {line}", err=True)


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
@click.option("--stall-timeout", "stall_timeout", default=0.0, type=float,
              help="Abort a harness that produces no output for this many seconds. "
                   "Default 0 (disabled): harnesses like 'claude -p' print nothing "
                   "until done, so a stall guard would kill long healthy tasks. "
                   "Only set this for harnesses that stream progress incrementally.")
@click.option("--log-dir", "log_dir", default="harness-logs", type=click.Path(),
              help="Where to write harness stdout/stderr logs")
@click.option("--report", "report_file", default=None, type=click.Path(),
              help="Write a JSON report to this path")
@click.option("--workspace-root", "workspace_root", default=None, type=click.Path(),
              help="Where to create per-testcase workspaces (default: OS temp dir). "
                   "Use a path your harness trusts if it gates edits under temp.")
@click.option("--stream/--no-stream", "stream", default=True,
              help="Stream harness output live to the screen (default: on).")
@click.option("--godot-binary", default="godot", help="Godot executable for L0/runtime verifiers")
def run_cmd(testcases_dir: str, testcase_id: str | None, harness_id: str,
            driver: str, patch_file: str | None, harness_cmd: str | None,
            timeout: float, stall_timeout: float, log_dir: str, report_file: str | None,
            workspace_root: str | None, stream: bool, godot_binary: str):
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
        # Stream each harness line live (prefixed) so a stuck prompt is visible
        # the instant it appears, not after the timeout fires.
        on_line = None
        if stream:
            def on_line(line: str) -> None:
                click.echo(f"  [{drv.label}] {line}", err=True)
        drv = CommandHarnessDriver(harness_cmd, timeout=timeout,
                                   log_dir=Path(log_dir), stall_timeout=stall_timeout,
                                   on_line=on_line)
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
            result = run_testcase(repo_root, tc, drv, harness_id, config,
                                  workspace_root=workspace_root)
        except Exception as e:
            # One un-runnable testcase (e.g. a git-type case with no repo root,
            # or a bad baseline_ref) must not kill the rest of the batch.
            click.echo(f"{tc.id}\t{tc.category}\terror\t0.00\t{e}")
            records.append({"testcase_id": tc.id, "category": tc.category,
                            "score": 0.0, "status": "error", "error": str(e)})
            continue
        total += result.score
        click.echo(f"{tc.id}\t{tc.category}\t{result.verifier_result.status}\t{result.score:.2f}")
        # Surface harness failures on screen immediately (don't make the user dig
        # through log files): if the command harness timed out or exited non-zero,
        # echo the tail of its log right after the result row.
        if isinstance(drv, CommandHarnessDriver) and drv.last_outcome is not None:
            _echo_harness_failure(tc.id, drv.last_outcome)
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
