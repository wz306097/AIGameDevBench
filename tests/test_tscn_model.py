from __future__ import annotations

from aigamedevbench.tscn_model import parse_canon, diff_scenes

BEFORE = """[gd_scene load_steps=2 format=3 uid="uid://aaa"]

[node name="Player" type="CharacterBody2D"]

[node name="Sprite" type="Sprite2D" parent="Player"]
position = Vector2(0, 0)
"""

AFTER_ADD_TIMER = """[gd_scene load_steps=2 format=3 uid="uid://aaa"]

[node name="Player" type="CharacterBody2D"]

[node name="Sprite" type="Sprite2D" parent="Player"]
position = Vector2(0, 0)

[node name="Cooldown" type="Timer" parent="Player"]
wait_time = 0.5
"""


def test_add_node_detected(tmp_path):
    b = tmp_path / "b.tscn"; b.write_text(BEFORE, encoding="utf-8")
    a = tmp_path / "a.tscn"; a.write_text(AFTER_ADD_TIMER, encoding="utf-8")
    delta = diff_scenes(parse_canon(b), parse_canon(a))
    assert "Player/Cooldown" in delta.added_nodes
    assert delta.removed_nodes == set()
    assert delta.changed_props == {}


def test_no_change_is_empty_delta(tmp_path):
    b = tmp_path / "b.tscn"; b.write_text(BEFORE, encoding="utf-8")
    a = tmp_path / "a.tscn"; a.write_text(BEFORE, encoding="utf-8")
    delta = diff_scenes(parse_canon(b), parse_canon(a))
    assert delta.added_nodes == set()
    assert delta.removed_nodes == set()
    assert delta.changed_props == {}
