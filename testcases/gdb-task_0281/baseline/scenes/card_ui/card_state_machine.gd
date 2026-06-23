extends Node

@export var initial_state: Node

var current_state
var states := {}


func init(card_ui) -> void:
	for child in get_children():
		states[child.state] = child
		child.card_ui = card_ui


func on_input(_event: InputEvent) -> void:
	pass


func on_gui_input(_event: InputEvent) -> void:
	pass


func on_mouse_entered() -> void:
	pass


func on_mouse_exited() -> void:
	pass


func _on_transition_requested(_from, _to: int) -> void:
	pass
