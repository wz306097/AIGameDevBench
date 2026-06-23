from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from godot_parser import load as gp_load


def _norm_value(v):
    if isinstance(v, float):
        return round(v, 4)
    return repr(v)


@dataclass
class CanonNode:
    path: str
    type: str
    props: dict = field(default_factory=dict)


@dataclass
class CanonScene:
    nodes: dict = field(default_factory=dict)
    connections: set = field(default_factory=set)
    resources: dict = field(default_factory=dict)


@dataclass
class SceneDelta:
    added_nodes: set = field(default_factory=set)
    removed_nodes: set = field(default_factory=set)
    changed_props: dict = field(default_factory=dict)
    added_conns: set = field(default_factory=set)
    removed_conns: set = field(default_factory=set)

    def is_empty(self) -> bool:
        return not (self.added_nodes or self.removed_nodes or self.changed_props
                    or self.added_conns or self.removed_conns)


def _node_path(node) -> str:
    name = getattr(node, "name", "")
    parent = getattr(node, "parent", None)
    if parent in (None, ".", ""):
        return str(name)
    return f"{parent}/{name}"


def parse_canon(tscn_path: Path) -> CanonScene:
    scene = gp_load(str(tscn_path))
    canon = CanonScene()
    for node in scene.get_nodes():
        path = _node_path(node)
        ntype = getattr(node, "type", "") or ""
        props = {}
        raw_props = getattr(node, "properties", {}) or {}
        for k, v in raw_props.items():
            props[str(k)] = _norm_value(v)
        canon.nodes[path] = CanonNode(path=path, type=ntype, props=props)
    for section in scene.get_sections("connection"):
        header = getattr(section, "header", None)
        attrs = getattr(header, "attributes", {}) if header else {}
        canon.connections.add((
            attrs.get("signal"), attrs.get("from"),
            attrs.get("to"), attrs.get("method"),
        ))
    return canon


def diff_scenes(before: CanonScene, after: CanonScene) -> SceneDelta:
    delta = SceneDelta()
    before_paths = set(before.nodes)
    after_paths = set(after.nodes)
    delta.added_nodes = after_paths - before_paths
    delta.removed_nodes = before_paths - after_paths
    for path in before_paths & after_paths:
        bp = before.nodes[path].props
        ap = after.nodes[path].props
        keys = set(bp) | set(ap)
        changed = {k: (bp.get(k), ap.get(k)) for k in keys if bp.get(k) != ap.get(k)}
        if changed:
            delta.changed_props[path] = changed
    delta.added_conns = after.connections - before.connections
    delta.removed_conns = before.connections - after.connections
    return delta
