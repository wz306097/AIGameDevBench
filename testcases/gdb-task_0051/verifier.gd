# Copied verbatim from GameDevBench test.gd by import_gamedevbench.py.
# Scored as a SINGLE overall checkpoint via its VALIDATION_PASSED/FAILED
# marker. For per-checkpoint partial credit, rewrite the reporting tail
# to print {"assertions":[...]} (see gdb-task_0002 for an example).
extends Node

func _ready() -> void:
	run_validation()

func fail(reason: String) -> void:
	print("VALIDATION_FAILED: %s" % reason)
	get_tree().quit(1)

func run_validation() -> void:
	var main = get_node_or_null("Main")
	if main == null:
		fail("Main scene is missing")
		return

	var player = main.get_node_or_null("Player")
	if player == null:
		fail("Player node not found under Main")
		return
	if not player is CharacterBody2D:
		fail("Player must be a CharacterBody2D")
		return

	var script = player.get_script()
	if script == null:
		fail("Player script is missing")
		return

	var sprite = player.get_node_or_null("Sprite2D")
	if sprite == null:
		fail("Sprite2D child missing on Player")
		return
	if sprite.texture == null:
		fail("Sprite2D must use the provided texture")
		return
	if sprite.texture.resource_path.find("tileYellow_02.png") == -1:
		fail("Sprite2D texture should come from tileYellow_02.png")
		return

	var collider = player.get_node_or_null("CollisionShape2D")
	if collider == null:
		fail("CollisionShape2D child missing on Player")
		return
	var shape = collider.shape
	if shape == null or not shape is RectangleShape2D:
		fail("Player collision must be a RectangleShape2D")
		return
	var expected_size = Vector2(32, 68)
	if not shape.size.is_equal_approx(expected_size):
		fail("Collision rectangle size should be %s" % expected_size)
		return

	var script_path = script.resource_path
	var script_file = FileAccess.open(script_path, FileAccess.READ)
	if script_file == null:
		fail("Unable to read player.gd")
		return
	var script_text = script_file.get_as_text()
	if script_text.find("@export var speed") == -1:
		fail("Player script must export a speed property")
		return
	if script_text.find("@export var jump_speed") == -1:
		fail("Player script must export a jump_speed property")
		return
	if script_text.find("@export var gravity") == -1:
		fail("Player script must export a gravity property")
		return
	if script_text.find("= 1200") == -1 or script_text.find("-1800") == -1 or script_text.find("= 4000") == -1:
		fail("Exported defaults should match 1200/-1800/4000")
		return
	if script_text.find("velocity.y += gravity * delta") == -1:
		fail("gravity must increment velocity.y each frame")
		return
	var axis_a = script_text.find("Input.get_axis(\"move_left\"")
	var axis_b = script_text.find("Input.get_axis('move_left'")
	if axis_a == -1 and axis_b == -1:
		fail("Player must read move_left/move_right via Input.get_axis")
		return
	if script_text.find("move_and_slide()") == -1:
		fail("move_and_slide must be called")
		return
	if script_text.find("Input.is_action_just_pressed(\"jump\"") == -1 and script_text.find("Input.is_action_just_pressed('jump'") == -1:
		fail("Jump should be triggered via Input.is_action_just_pressed(\"jump\")")
		return
	if script_text.find("is_on_floor()") == -1:
		fail("Jump logic must check is_on_floor()")
		return

	print("VALIDATION_PASSED: Player node and script match the tutorial requirements")
	get_tree().quit()
