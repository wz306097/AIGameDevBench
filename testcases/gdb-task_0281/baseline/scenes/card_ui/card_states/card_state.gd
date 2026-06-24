extends Node

enum State {BASE, CLICKED, DRAGGING, RELEASED}

signal transition_requested(from, to)

@export var state := State.BASE

var card_ui


func enter() -> void:
	pass


func exit() -> void:
	pass


func on_input(_event: InputEvent) -> void:
	pass


func on_gui_input(_event: InputEvent) -> void:
	pass


func on_mouse_entered() -> void:
	pass


func on_mouse_exited() -> void:
	pass
