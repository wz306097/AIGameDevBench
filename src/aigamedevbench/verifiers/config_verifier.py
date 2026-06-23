from __future__ import annotations

import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from aigamedevbench.result import CheckResult, VerifierResult
from aigamedevbench.testcase import Testcase
from aigamedevbench.verifiers.base import register


def _flatten(obj, prefix: str, out: dict) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _flatten(v, f"{prefix}.{i}", out)
    else:
        out[prefix] = obj


def flatten_config(path: Path) -> dict[str, object]:
    out: dict[str, object] = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".json":
        _flatten(json.loads(text), "", out)
    elif path.suffix == ".toml":
        _flatten(tomllib.loads(text), "", out)
    elif path.suffix == ".tres":
        try:
            from godot_parser import load as gp_load
            scene = gp_load(str(path))
            for section in scene.get_sections():
                props = getattr(section, "properties", {}) or {}
                for k, v in props.items():
                    out[str(k)] = v
        except Exception:
            for line in text.splitlines():
                if "=" in line and not line.strip().startswith("["):
                    k, _, v = line.partition("=")
                    out[k.strip()] = v.strip()
    return out


def _glob(workspace: Path, pattern: str) -> list[Path]:
    if "{" in pattern and "}" in pattern:
        head, _, rest = pattern.partition("{")
        opts, _, tail = rest.partition("}")
        results: list[Path] = []
        for opt in opts.split(","):
            results.extend(workspace.glob(head + opt + tail))
        return results
    return list(workspace.glob(pattern))


def _matches(value, expected, tol) -> bool:
    if isinstance(expected, (int, float)) and isinstance(value, (int, float)):
        return abs(float(value) - float(expected)) <= float(tol)
    return value == expected


@register("py_config")
class ConfigVerifier:
    def verify(self, testcase: Testcase, workspace: Path) -> VerifierResult:
        spec_path = testcase.dir / "expected.json"
        if not spec_path.exists():
            return VerifierResult.error_result(testcase.category, "missing expected.json")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        checks: list[CheckResult] = []
        for field in spec.get("fields", []):
            name = field["name"]
            aliases = set(field.get("aliases", [name]))
            expected = field["expected"]
            tol = field.get("tol", 1e-6)
            base = field.get("base")
            must_differ = field.get("must_differ_from_base", False)
            found_value = None
            for cfg_path in _glob(workspace, field.get("files_glob", "**/*")):
                if not cfg_path.is_file():
                    continue
                flat = flatten_config(cfg_path)
                for key, val in flat.items():
                    leaf = key.split(".")[-1]
                    if leaf in aliases and _matches(val, expected, tol):
                        found_value = val
                        break
                if found_value is not None:
                    break
            ok = found_value is not None
            if ok and must_differ and base is not None and _matches(found_value, base, tol):
                ok = False
            checks.append(CheckResult(name, ok, expected=expected, actual=found_value))
        return VerifierResult.from_checks(checks, testcase.category, testcase.scoring_mode)
