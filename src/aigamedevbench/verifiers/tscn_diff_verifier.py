from __future__ import annotations

import json
from pathlib import Path

from aigamedevbench.result import CheckResult, VerifierResult
from aigamedevbench.testcase import Testcase
from aigamedevbench.tscn_model import parse_canon, diff_scenes
from aigamedevbench.verifiers.base import register


@register("py_tscn_diff")
class TscnDiffVerifier:
    def verify(self, testcase: Testcase, workspace: Path) -> VerifierResult:
        spec_path = testcase.dir / "expected_delta.json"
        if not spec_path.exists():
            return VerifierResult.error_result(testcase.category, "missing expected_delta.json")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        baseline = testcase.dir / spec["baseline_scene"]
        after = workspace / spec["scene"]
        if not after.exists():
            return VerifierResult.error_result(testcase.category, f"scene not found: {spec['scene']}")
        delta = diff_scenes(parse_canon(baseline), parse_canon(after))

        exp = spec["expected"]
        exp_added = set(exp.get("added_nodes", []))
        exp_removed = set(exp.get("removed_nodes", []))
        exp_changed = set(exp.get("changed_props", {}).keys())

        intended = (exp_added <= delta.added_nodes
                    and exp_removed <= delta.removed_nodes
                    and exp_changed <= set(delta.changed_props.keys()))

        extra_added = delta.added_nodes - exp_added
        extra_removed = delta.removed_nodes - exp_removed
        extra_changed = set(delta.changed_props.keys()) - exp_changed
        side_effects = extra_added | extra_removed | extra_changed | delta.added_conns | delta.removed_conns
        no_side = len(side_effects) == 0

        checks = [
            CheckResult("intended_change", intended,
                        detail=f"expected added={sorted(exp_added)}"),
            CheckResult("no_side_effects", no_side,
                        detail=f"unexpected={sorted(str(s) for s in side_effects)}"),
        ]
        return VerifierResult.from_checks(checks, testcase.category, "tristate")
