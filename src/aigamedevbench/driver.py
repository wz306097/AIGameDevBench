from __future__ import annotations

from pathlib import Path
from typing import Protocol

from aigamedevbench.workspace import apply_patch


class HarnessDriver(Protocol):
    def run(self, task: str, workspace: Path) -> None: ...


class NoOpDriver:
    def run(self, task: str, workspace: Path) -> None:
        return None


class PatchDriver:
    def __init__(self, patch_text: str):
        self.patch_text = patch_text

    def run(self, task: str, workspace: Path) -> None:
        apply_patch(workspace, self.patch_text)
