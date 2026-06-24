# Copied verbatim from GameDevBench test.gd by import_gamedevbench.py.
# Scored as a SINGLE overall checkpoint via its VALIDATION_PASSED/FAILED
# marker. For per-checkpoint partial credit, rewrite the reporting tail
# to print {"assertions":[...]} (see gdb-task_0002 for an example).
extends Node

const ENEMY_SCRIPT_PATH := "res://scripts/enemy.gd"
const ENEMY_TEXTURE_PATH := "res://assets/sprites/towerDefense_tile245.png"
const TARGET_TEXTURE_PATH := "res://assets/sprites/icon.svg"

func _ready():
	run_validation()

func run_validation():
	var main_node := get_node_or_null("Main")
	if main_node == null:
		fail("Main node not found")
		return

	var nav_region := main_node.get_node_or_null("NavigationRegion2D")
	if nav_region == null or not (nav_region is NavigationRegion2D):
		fail("NavigationRegion2D missing under Main")
		return
	if nav_region.navigation_polygon == null:
		fail("NavigationRegion2D must have a NavigationPolygon assigned")
		return

	var enemy := main_node.get_node_or_null("Enemy")
	if enemy == null:
		fail("Enemy node not found")
		return
	if not (enemy is CharacterBody2D):
		fail("Enemy must be CharacterBody2D")
		return

	if enemy.script == null or enemy.script.resource_path != ENEMY_SCRIPT_PATH:
		fail("Enemy must have res://scripts/enemy.gd attached")
		return

	var nav_root := enemy.get_node_or_null("Navigation")
	if nav_root == null:
		fail("Enemy is missing Navigation node")
		return
	var agent := nav_root.get_node_or_null("NavigationAgent2D")
	if agent == null or not (agent is NavigationAgent2D):
		fail("NavigationAgent2D missing under Enemy/Navigation")
		return
	if agent.path_postprocessing != NavigationPathQueryParameters2D.PathPostProcessing.PATH_POSTPROCESSING_CORRIDORFUNNEL:
		fail("NavigationAgent2D path_postprocessing must be Corridor")
		return
	if not agent.debug_enabled:
		fail("NavigationAgent2D debug_enabled must be true")
		return

	var timer := nav_root.get_node_or_null("Timer")
	if timer == null or not (timer is Timer):
		fail("Timer missing under Enemy/Navigation")
		return
	if abs(timer.wait_time - 0.1) > 0.0001:
		fail("Timer wait_time must be 0.1")
		return
	if timer.is_stopped():
		fail("Timer autostart must be enabled")
		return
	if not timer.timeout.is_connected(Callable(enemy, "_on_timer_timeout")):
		fail("Timer timeout must be connected to Enemy._on_timer_timeout")
		return

	var enemy_sprite := enemy.get_node_or_null("Sprite2D")
	if enemy_sprite == null or not (enemy_sprite is Sprite2D):
		fail("Enemy Sprite2D missing")
		return
	if enemy_sprite.texture == null or enemy_sprite.texture.resource_path != ENEMY_TEXTURE_PATH:
		fail("Enemy Sprite2D must use towerDefense_tile245.png")
		return

	var enemy_shape := enemy.get_node_or_null("CollisionShape2D")
	if enemy_shape == null or not (enemy_shape is CollisionShape2D):
		fail("Enemy CollisionShape2D missing")
		return
	if enemy_shape.shape == null or not (enemy_shape.shape is CircleShape2D):
		fail("Enemy CollisionShape2D must be a CircleShape2D")
		return
	if abs(enemy_shape.shape.radius - 12.0) > 0.01:
		fail("Enemy CircleShape2D radius must be 12")
		return

	var target := main_node.get_node_or_null("Target")
	if target == null or not (target is Area2D):
		fail("Target Area2D missing")
		return

	var target_sprite := target.get_node_or_null("Sprite2D")
	if target_sprite == null or not (target_sprite is Sprite2D):
		fail("Target Sprite2D missing")
		return
	if target_sprite.texture == null or target_sprite.texture.resource_path != TARGET_TEXTURE_PATH:
		fail("Target Sprite2D must use icon.svg")
		return
	if target_sprite.scale != Vector2(0.15625, 0.15625):
		fail("Target Sprite2D scale must be 0.15625, 0.15625")
		return

	var target_shape := target.get_node_or_null("CollisionShape2D")
	if target_shape == null or not (target_shape is CollisionShape2D):
		fail("Target CollisionShape2D missing")
		return
	if target_shape.shape == null or not (target_shape.shape is RectangleShape2D):
		fail("Target CollisionShape2D must be a RectangleShape2D")
		return

	var target_path = enemy.get("target")
	if not str(target_path).contains("Target"):
		fail("Enemy target export must point to Target, got %s instead" % str(target_path))
		return

	if not script_contains_required_strings(ENEMY_SCRIPT_PATH, ["get_next_path_position", "target_position", "move_and_slide"]):
		fail("Enemy script missing pathfinding logic")
		return
	var before_target_pos = agent.target_position
	enemy._on_timer_timeout()
	var expected_target_pos = target.global_position
	if agent.target_position != expected_target_pos:
		fail("Timer timeout must update NavigationAgent2D target_position to Target global position")
		return
	if agent.target_position == before_target_pos and before_target_pos != expected_target_pos:
		fail("NavigationAgent2D target_position did not change after timeout")
		return

	pass_validation()

func script_contains_required_strings(path: String, required: Array) -> bool:
	if not FileAccess.file_exists(path):
		return false
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return false
	var text := file.get_as_text()
	file.close()
	for token in required:
		if text.find(token) == -1:
			return false
	return true

func fail(reason: String):
	print("VALIDATION_FAILED: %s" % reason)
	get_tree().quit(1)

func pass_validation():
	print("VALIDATION_PASSED: Task completed successfully")
	get_tree().quit(0)
