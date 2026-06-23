from __future__ import annotations

import json
import re
from pathlib import Path

from aigamedevbench.result import CheckResult, VerifierResult
from aigamedevbench.testcase import Testcase
from aigamedevbench.verifiers.base import register

_RES_RE = re.compile(r'"(res://[^"]+)"')
_EXTENDS_RE = re.compile(r'^\s*extends\s+([A-Za-z_][A-Za-z0-9_]*)', re.MULTILINE)
_IMPORT_RE = re.compile(r'(?:preload|load)\s*\(\s*"(res://[^"]+)"\s*\)')


def find_res_paths(gd_source: str) -> list[str]:
    return _RES_RE.findall(gd_source)


def find_extends(gd_source: str) -> str | None:
    m = _EXTENDS_RE.search(gd_source)
    return m.group(1) if m else None


def find_imports(gd_source: str) -> list[str]:
    return _IMPORT_RE.findall(gd_source)


def _check_rule(rule: dict, sources: dict[str, str]) -> bool:
    rtype = rule["type"]
    if rtype == "forbid_import_glob":
        needle = rule["glob"]
        for src in sources.values():
            for imp in find_imports(src):
                if needle in imp:
                    return False
        return True
    if rtype == "forbid_hardcoded_res_path":
        for src in sources.values():
            imports = set(find_imports(src))
            for path in find_res_paths(src):
                if path not in imports:
                    return False
        return True
    if rtype == "require_extends":
        base = rule["base"]
        return any(find_extends(src) == base for src in sources.values())
    return True


@register("py_gdscript_ast")
class ArchVerifier:
    def verify(self, testcase: Testcase, workspace: Path) -> VerifierResult:
        spec_path = testcase.dir / "arch_rules.json"
        if not spec_path.exists():
            return VerifierResult.error_result(testcase.category, "missing arch_rules.json")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        sources: dict[str, str] = {}
        for rel in spec.get("target_files", []):
            p = workspace / rel
            if p.exists():
                sources[rel] = p.read_text(encoding="utf-8", errors="replace")
        if not sources:
            return VerifierResult.error_result(testcase.category, "no target files found")

        penalty = 0
        checks: list[CheckResult] = []
        for rule in spec.get("rules", []):
            ok = _check_rule(rule, sources)
            if not ok:
                penalty += rule.get("weight", 0)
            checks.append(CheckResult(rule["id"], ok, expected=rule.get("weight", 0)))
        score = max(0.0, 100 - penalty) / 100.0
        status = VerifierResult._status_from_score(score)
        return VerifierResult(score=score, status=status, checks=checks, category=testcase.category)
