from __future__ import annotations

import subprocess
import time
from pathlib import Path

# Windows hands back "Permission denied" / "Access is denied" when antivirus or
# the Search indexer transiently locks a just-written file under .git/objects.
# It's a race, not a real failure: the same command succeeds on a quick retry.
_TRANSIENT_MARKERS = ("permission denied", "access is denied",
                      "unable to write file", "failed to insert into database")
_MAX_ATTEMPTS = 4
_RETRY_BACKOFF_S = 0.25


def _looks_transient(stderr: str) -> bool:
    low = stderr.lower()
    return any(m in low for m in _TRANSIENT_MARKERS)


def git_run(args: list[str], cwd: Path | str, input: str | None = None) -> str:
    last: subprocess.CalledProcessError | None = None
    for attempt in range(_MAX_ATTEMPTS):
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            input=input,
        )
        if result.returncode == 0:
            return result.stdout
        # Surface stderr in the exception so failures are diagnosable instead of
        # a bare "returned non-zero exit status 128".
        last = subprocess.CalledProcessError(
            result.returncode, ["git"] + args,
            output=result.stdout, stderr=result.stderr,
        )
        if attempt < _MAX_ATTEMPTS - 1 and _looks_transient(result.stderr):
            time.sleep(_RETRY_BACKOFF_S * (attempt + 1))
            continue
        break
    msg = (last.stderr or "").strip()
    raise RuntimeError(
        f"git {' '.join(args)} failed (exit {last.returncode})"
        + (f": {msg}" if msg else "")
    ) from last


def get_repo_root(cwd: Path | str) -> Path:
    output = git_run(["rev-parse", "--show-toplevel"], cwd=cwd)
    return Path(output.strip())
