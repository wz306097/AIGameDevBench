# Copied verbatim from GameDevBench test.gd by import_gamedevbench.py.
# Scored as a SINGLE overall checkpoint via its VALIDATION_PASSED/FAILED
# marker. For per-checkpoint partial credit, rewrite the reporting tail
# to print {"assertions":[...]} (see gdb-task_0002 for an example).
extends Node

func _ready() -> void:
	await get_tree().process_frame
	run_validation()

func run_validation() -> void:
	if not InputMap.has_action("interact"):
		return _fail("Project must define an 'interact' input action")
	var events := InputMap.action_get_events("interact")
	var has_f_key := false
	for event in events:
		if event is InputEventKey and event.physical_keycode == KEY_F:
			has_f_key = true
			break
	if not has_f_key:
		return _fail("'interact' action must be bound to the F key")
	var main_node = get_node_or_null("Main")
	if main_node == null:
		return _fail("Main scene was not instanced")
	var interaction_area: PlayerInteractionHandler = main_node.get_node_or_null("PlayerBody/InteractionArea")
	if interaction_area == null:
		return _fail("InteractionArea node missing from PlayerBody")
	if interaction_area.collision_layer != 0 or interaction_area.collision_mask != 2:
		return _fail("InteractionArea collision filtering must be layer 0 / mask 2")
	var entered_callable := Callable(interaction_area, "_on_body_entered")
	var exited_callable := Callable(interaction_area, "_on_body_exited")
	if not interaction_area.is_connected("body_entered", entered_callable):
		return _fail("body_entered signal must be connected to _on_body_entered")
	if not interaction_area.is_connected("body_exited", exited_callable):
		return _fail("body_exited signal must be connected to _on_body_exited")
	if interaction_area.item_types.size() != 2:
		return _fail("InteractionArea.item_types must contain two templates")
	var names := interaction_area.item_types.map(func(item: ItemData): return item.item_name)
	if not names.has("Test Cube") or not names.has("Test Sphere"):
		return _fail("ItemData resources must be assigned for Test Cube and Test Sphere")
	var cube: InteractableItem = main_node.get_node_or_null("ItemPickupCube")
	var sphere: InteractableItem = main_node.get_node_or_null("ItemPickupSphere")
	if cube == null or sphere == null:
		return _fail("Main scene must instance both pickup prefabs")
	interaction_area.nearby_bodies.clear()
	interaction_area._on_body_entered(cube)
	if not cube.item_highlight_mesh.visible:
		return _fail("gain_focus should show the highlight when entering the area")
	interaction_area._on_body_entered(sphere)
	var picked := []
	interaction_area.item_picked_up.connect(func(item_data: ItemData): picked.append(item_data.item_name))
	var event := InputEventAction.new()
	event.action = "interact"
	event.pressed = true
	interaction_area._input(event)
	if cube in interaction_area.nearby_bodies:
		return _fail("Nearest item should be removed from nearby_bodies after pickup")
	if not cube.is_queued_for_deletion():
		return _fail("Picked item must be queued for deletion")
	if picked.size() == 0 or picked[0] != "Test Cube":
		return _fail("Picking up the first item must emit Test Cube")
	interaction_area._on_body_exited(sphere)
	if sphere in interaction_area.nearby_bodies:
		return _fail("_on_body_exited must remove the body from nearby_bodies")
	if sphere.item_highlight_mesh.visible:
		return _fail("lose_focus must hide the highlight on exit")
	print("VALIDATION_PASSED: Interaction area picks and tracks nearby items")
	get_tree().quit()

func _fail(message: String) -> void:
	print("VALIDATION_FAILED: %s" % message)
	get_tree().quit(1)
