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


# --- L0: GDScript syntax + headless scene load ---

def check_gd_syntax(project_root: Path, gd_files: list[str]) -> list[str]:
    issues = []
    for gd_rel in gd_files:
        gd_path = project_root / gd_rel
        if not gd_path.exists():
            issues.append(f"{gd_rel}: file not found")
            continue
        content = gd_path.read_text(encoding="utf-8", errors="replace")
        paren_depth = 0
        for i, char in enumerate(content):
            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1
            if paren_depth < 0:
                issues.append(f"{gd_rel}: unmatched ')' near character {i}")
                break
        if paren_depth > 0:
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
                    capture_output=True, text=True, timeout=10,
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
    scenes = [f for f in changed_files if f.endswith(".tscn")]
    l0_pass, l0_details = run_l0(repo_root, scenes, godot_binary)
    l1_pass, l1_details = run_l1(repo_root, changed_files)
    return VerificationResult(
        l0_pass=l0_pass, l1_pass=l1_pass,
        l0_details=l0_details, l1_details=l1_details,
    )
