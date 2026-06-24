# Copied verbatim from GameDevBench test.gd by import_gamedevbench.py.
# Scored as a SINGLE overall checkpoint via its VALIDATION_PASSED/FAILED
# marker. For per-checkpoint partial credit, rewrite the reporting tail
# to print {"assertions":[...]} (see gdb-task_0002 for an example).
extends Node

const PLAYER_SCENE := "res://scenes/player.tscn"
const SPEED := 1200.0
const JUMP_SPEED := -1800.0

func _ready() -> void:
	var player_scene: PackedScene = load(PLAYER_SCENE)
	if player_scene == null:
		fail("Failed to load Player scene.")
		return

	var player: CharacterBody2D = player_scene.instantiate()
	if player == null:
		fail("Failed to instance Player scene.")
		return

	# Create a floor
	var floor := StaticBody2D.new()
	var floor_shape = RectangleShape2D.new()
	floor_shape.extents = Vector2(1000, 10)
	var floor_collider = CollisionShape2D.new()
	floor_collider.shape = floor_shape
	floor.add_child(floor_collider)
	floor.position = Vector2(0, 600)

	# Add to tree
	add_child(player)
	add_child(floor)
	player.position = Vector2(0, 550)

	# Start tests
	test_suite(player)


func test_suite(player: CharacterBody2D) -> void:    
	# --- Basic property checks ---
	if not player.has_method("_physics_process"):
		fail("Player script is missing _physics_process(delta).")
		return
		
	if not player.get("friction") is float or not player.get("acceleration") is float:
		fail("Friction and acceleration must be exported float variables.")
		return
		
	if not is_equal_approx(player.get("friction"), 0.1):
		fail("Default friction should be 0.1.")
		return
		
	if not is_equal_approx(player.get("acceleration"), 0.25):
		fail("Default acceleration should be 0.25.")
		return

	# --- Simulation tests ---
	await test_acceleration(player)

	await test_friction(player)

	await test_jump(player)
	
	await get_tree().process_frame
	
	# Final success
	print("VALIDATION_PASSED: Player controller uses lerp-based acceleration/friction and preserves jump.")

	# If all tests pass
	get_tree().quit(0)
	


func test_acceleration(player: CharacterBody2D) -> void:
	Input.action_press("move_right")
	var initial_velocity_x = player.velocity.x
	
	await get_tree().physics_frame
	await get_tree().physics_frame

	var velocity_after_2_frames = player.velocity.x
	if velocity_after_2_frames <= initial_velocity_x:
		fail("Player is not accelerating to the right. Velocity did not increase.")
		return
		
	if velocity_after_2_frames >= SPEED:
		fail("Player accelerated too fast. Should be a gradual lerp.")
		return

	Input.action_release("move_right")

func test_friction(player: CharacterBody2D) -> void:
	# Ensure player has some velocity
	Input.action_press("move_right")
	await get_tree().physics_frame
	await get_tree().physics_frame
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("move_right")
	
	var initial_velocity_x = player.velocity.x
	if initial_velocity_x <= 0:
		fail("Player should have positive velocity before friction test.")
		return

	await get_tree().physics_frame
	await get_tree().physics_frame
	
	var velocity_after_2_frames = player.velocity.x
	if velocity_after_2_frames >= initial_velocity_x:
		fail("Player is not decelerating. Check friction implementation.")
		return

	var is_stopping = false
	for i in range(200): # More frames to be sure
		await get_tree().physics_frame
		if abs(player.velocity.x) < 1.0:
			is_stopping = true
			break
			
	if not is_stopping:
		fail("Player did not come to a stop. Check friction lerp.")
		return
		
	return


func test_jump(player: CharacterBody2D) -> void:
	# Ensure player is on the floor
	player.position = Vector2(0, 550)
	for i in range(10):
		await get_tree().physics_frame

	if not player.is_on_floor():
		fail("Could not get player to be on the floor to test jump.")
		return

	Input.action_press("jump")
	await get_tree().physics_frame
	await get_tree().physics_frame
	
	if not player.velocity.y < JUMP_SPEED / 2.0:
		fail("Player jump velocity is not correct. Expected approx %f, got %f" % [JUMP_SPEED, player.velocity.y])
		
		return
		 
	Input.action_release("jump")


func fail(reason: String) -> void:
	print("VALIDATION_FAILED: %s" % reason)
	get_tree().quit(1)
