# Copied verbatim from GameDevBench test.gd by import_gamedevbench.py.
# Scored as a SINGLE overall checkpoint via its VALIDATION_PASSED/FAILED
# marker. For per-checkpoint partial credit, rewrite the reporting tail
# to print {"assertions":[...]} (see gdb-task_0002 for an example).
extends Node

const MAIN_SCENE := preload("res://scenes/main.tscn")


func _ready() -> void:
	await run_validation()


func assert_or_fail(condition: bool, reason: String) -> bool:
	if not condition:
		print("VALIDATION_FAILED: %s" % reason)
		get_tree().quit(1)
		return false
	return true


func make_mouse_button_event(button_index: MouseButton, pressed: bool) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = button_index
	event.pressed = pressed
	event.position = Vector2(132, 88)
	event.global_position = event.position
	return event


func make_mouse_motion_event(position: Vector2) -> InputEventMouseMotion:
	var event := InputEventMouseMotion.new()
	event.position = position
	event.global_position = position
	return event


func run_validation() -> void:
	var main = MAIN_SCENE.instantiate()
	add_child(main)
	await get_tree().process_frame
	await get_tree().process_frame

	var hand = main.get_node_or_null("HUD/CardRow")
	if not assert_or_fail(hand != null, "Main must provide HUD/CardRow"):
		return
	if not assert_or_fail(hand.get_child_count() == 3, "Main must spawn three cards into CardRow"):
		return

	var card = hand.get_child(0)
	var machine = card.get_node_or_null("CardStateMachine")
	var base_state = card.get_node_or_null("CardStateMachine/CardBaseState")
	var clicked_state = card.get_node_or_null("CardStateMachine/CardClickedState")
	var dragging_state = card.get_node_or_null("CardStateMachine/CardDraggingState")
	var drop_area = main.get_node_or_null("PlayZone")
	var ui_layer = main.get_node_or_null("HUD")

	if not assert_or_fail(machine != null, "CardUI must contain a CardStateMachine"):
		return
	if not assert_or_fail(base_state != null and clicked_state != null and dragging_state != null, "CardUI must provide the drag state nodes"):
		return
	if not assert_or_fail(machine.current_state == base_state, "CardStateMachine must enter CardBaseState on ready"):
		return

	var initial_index = card.get_index()
	card._on_gui_input(make_mouse_button_event(MOUSE_BUTTON_LEFT, true))
	await get_tree().process_frame

	if not assert_or_fail(machine.current_state == clicked_state, "Left-clicking a card must enter the clicked state"):
		return
	if not assert_or_fail(card.original_index == initial_index, "Clicked state must record the card's original CardRow index"):
		return
	if not assert_or_fail(card.drop_point_detector.monitoring, "Clicked state must enable DropPointDetector.monitoring"):
		return

	card._input(make_mouse_motion_event(Vector2(118, 38)))
	await get_tree().process_frame

	if not assert_or_fail(machine.current_state == dragging_state, "Mouse motion from the clicked state must enter the dragging state"):
		return
	if not assert_or_fail(card.get_parent() == ui_layer, "Dragging state must reparent the card into the overlay_layer group"):
		return

	card._input(make_mouse_button_event(MOUSE_BUTTON_LEFT, false))
	await get_tree().process_frame

	if not assert_or_fail(machine.current_state == dragging_state, "Dragging must ignore release confirmation before the minimum drag threshold elapses"):
		return

	card._input(make_mouse_button_event(MOUSE_BUTTON_RIGHT, true))
	await get_tree().process_frame
	await get_tree().process_frame

	if not assert_or_fail(machine.current_state == base_state, "Right-clicking while dragging must snap the card back to the base state"):
		return
	if not assert_or_fail(card.get_parent() == hand, "Cancelling a drag must reparent the card back into CardRow"):
		return
	if not assert_or_fail(hand.get_child(initial_index) == card, "Cancelled drags must restore the card's original CardRow slot"):
		return
	if not assert_or_fail(not card.drop_point_detector.monitoring, "Base state must reset DropPointDetector.monitoring to false"):
		return

	card._on_drop_point_detector_area_entered(drop_area)
	card._on_drop_point_detector_area_entered(drop_area)
	if not assert_or_fail(card.targets.size() == 1, "DropPointDetector area enters must not duplicate targets"):
		return
	card._on_drop_point_detector_area_exited(drop_area)
	if not assert_or_fail(card.targets.is_empty(), "DropPointDetector area exits must remove the target"):
		return

	card._on_gui_input(make_mouse_button_event(MOUSE_BUTTON_LEFT, true))
	await get_tree().process_frame
	card._input(make_mouse_motion_event(Vector2(118, 38)))
	await get_tree().process_frame
	card._on_drop_point_detector_area_entered(drop_area)
	await get_tree().create_timer(0.05).timeout
	card._input(make_mouse_button_event(MOUSE_BUTTON_LEFT, false))
	await get_tree().process_frame
	await get_tree().process_frame

	if not assert_or_fail(not is_instance_valid(card), "Releasing over PlayZone after the drag threshold must play and remove the card"):
		return
	if not assert_or_fail(hand.get_child_count() == 2, "Playing a card must remove it from CardRow"):
		return

	print("VALIDATION_PASSED: Card dragging enters the correct states, cancels back to CardRow, and plays over PlayZone")
	get_tree().quit()
