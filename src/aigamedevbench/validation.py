from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VerificationResult:
    l0_pass: bool = True
    l1_pass: bool = True
    l0_details: list[str] = field(default_factory=list)
    l1_details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "l0_pass": self.l0_pass,
            "l1_pass": self.l1_pass,
            "l0_details": self.l0_details,
            "l1_details": self.l1_details,
        }


# --- Godot import cache ---

def godot_import(project_root: Path, godot_binary: str = "godot",
                 timeout: int = 120) -> None:
    """Build the Godot import cache (.godot/imported/*) for the workspace.

    Folder-type baselines ship without .godot/ (the importer strips it), so any
    scene referencing an imported resource (a PNG as CompressedTexture2D) fails
    to load until an import pass runs. This must happen before L0 boots changed
    scenes AND before the runtime verifier boots its scene; both share the same
    workspace, so a single pass here covers both. Idempotent: if the cache is
    already present Godot re-imports nothing. Best-effort — a failure here just
    leaves the cache absent, and the downstream load error is reported normally.
    """
    if shutil.which(godot_binary) is None:
        return
    try:
        subprocess.run(
            [godot_binary, "--headless", "--path", str(project_root), "--import"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


# --- L0: GDScript syntax + headless scene load ---

def _count_paren_depth(content: str) -> int | None:
    """Net paren depth, ignoring parens inside string literals and # comments.

    Returns the remaining open-paren count (0 = balanced, >0 = unclosed), or
    None if a ')' ever closes below zero (unmatched ')'). GDScript strings use
    ' or " (no f-strings); a backslash escapes the next char inside a string.
    Counting raw characters would false-positive on code like
    `name.split("(")[0]`, so string/comment regions are skipped.
    """
    depth = 0
    quote: str | None = None
    escaped = False
    for char in content:
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\" and quote != "\n":
                escaped = True  # backslash escapes only inside string literals
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "#":
            # Comment runs to end of line: treat newline as its closing "quote".
            quote = "\n"
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return None
    return depth


def check_gd_syntax(project_root: Path, gd_files: list[str]) -> list[str]:
    issues = []
    for gd_rel in gd_files:
        gd_path = project_root / gd_rel
        if not gd_path.exists():
            issues.append(f"{gd_rel}: file not found")
            continue
        content = gd_path.read_text(encoding="utf-8", errors="replace")
        paren_depth = _count_paren_depth(content)
        if paren_depth is None:
            issues.append(f"{gd_rel}: unmatched ')'")
        elif paren_depth > 0:
            issues.append(f"{gd_rel}: unclosed '(' ({paren_depth} remaining)")

        func_no_colon = re.compile(r"^func\s+\w+\s*\([^)]*\)\s*$", re.MULTILINE)
        for match in func_no_colon.finditer(content):
            line_num = content[:match.start()].count("\n") + 1
            issues.append(f"{gd_rel}:{line_num}: function definition missing ':'")
    return issues


def run_l0(project_root: Path, scenes: list[str], godot_binary: str = "godot") -> tuple[bool, list[str]]:
    issues: list[str] = []
    gd_files = [str(p.relative_to(project_root)) for p in project_root.rglob("*.gd")]
    issues.extend(check_gd_syntax(project_root, gd_files))

    if shutil.which(godot_binary):
        for scene in scenes:
            try:
                result = subprocess.run(
                    [godot_binary, "--headless", "--path", str(project_root), scene, "--quit-after", "2"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=10,
                )
                if result.returncode != 0:
                    issues.append(f"L0 crash: {scene} exited with code {result.returncode}")
                for line in (result.stderr or "").splitlines():
                    if "ERROR" in line:
                        issues.append(f"L0 crash: {scene}: {line.strip()}")
            except subprocess.TimeoutExpired:
                issues.append(f"L0 crash: {scene} timed out after 10s")
            except FileNotFoundError:
                issues.append(f"L0 crash: godot binary '{godot_binary}' not found")
                break
    return len(issues) == 0, issues


# --- L1: scene resource + signal target integrity ---

def check_script_references(project_root: Path, tscn_files: list[str]) -> list[str]:
    issues = []
    ext_resource_re = re.compile(r'\[ext_resource\s.*?path="res://([^"]+)"')
    for tscn_rel in tscn_files:
        tscn_path = project_root / tscn_rel
        if not tscn_path.exists():
            continue
        content = tscn_path.read_text(encoding="utf-8", errors="replace")
        for match in ext_resource_re.finditer(content):
            ref_path = match.group(1)
            if not (project_root / ref_path).exists():
                issues.append(f"{tscn_rel}: missing resource '{ref_path}'")
    return issues


def check_signal_targets(project_root: Path, tscn_files: list[str]) -> list[str]:
    issues = []
    connection_re = re.compile(
        r'\[connection\s+signal="([^"]+)"\s+from="([^"]+)"\s+to="([^"]+)"\s+method="([^"]+)"\]'
    )
    ext_script_re = re.compile(r'\[ext_resource\s.*?type="Script"\s.*?path="res://([^"]+)"')
    for tscn_rel in tscn_files:
        tscn_path = project_root / tscn_rel
        if not tscn_path.exists():
            continue
        content = tscn_path.read_text(encoding="utf-8", errors="replace")
        defined_methods: set[str] = set()
        for sp in ext_script_re.findall(content):
            script_full = project_root / sp
            if script_full.exists():
                script_content = script_full.read_text(encoding="utf-8", errors="replace")
                func_re = re.compile(r"^func\s+(\w+)\s*\(", re.MULTILINE)
                defined_methods.update(func_re.findall(script_content))
        for match in connection_re.finditer(content):
            signal_name = match.group(1)
            method_name = match.group(4)
            if method_name not in defined_methods:
                issues.append(
                    f"{tscn_rel}: signal '{signal_name}' connected to method '{method_name}' which is not defined"
                )
    return issues


def run_l1(project_root: Path, changed_files: list[str]) -> tuple[bool, list[str]]:
    tscn_files = [f for f in changed_files if f.endswith(".tscn")]
    if not tscn_files:
        tscn_files = [str(p.relative_to(project_root)) for p in project_root.rglob("*.tscn")]
    if not tscn_files:
        return True, []
    issues: list[str] = []
    issues.extend(check_script_references(project_root, tscn_files))
    issues.extend(check_signal_targets(project_root, tscn_files))
    return len(issues) == 0, issues


def run_validation(repo_root: Path, changed_files: list[str], config: dict) -> VerificationResult:
    godot_binary = config.get("global", {}).get("godot", {}).get("binary", "godot")
    # Build the import cache once before any headless boot (L0 here, and the
    # runtime verifier later) so scenes with imported resources can load.
    godot_import(repo_root, godot_binary)
    scenes = [f for f in changed_files if f.endswith(".tscn")]
    l0_pass, l0_details = run_l0(repo_root, scenes, godot_binary)
    l1_pass, l1_details = run_l1(repo_root, changed_files)
    return VerificationResult(
        l0_pass=l0_pass, l1_pass=l1_pass,
        l0_details=l0_details, l1_details=l1_details,
    )
