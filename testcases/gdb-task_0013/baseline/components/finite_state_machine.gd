class_name FiniteStateMachine
extends RefCounted

# TODO: Add state_changed signal

var state: State


func change_state(new_state: State) -> void:
	# TODO: Implement state transition logic
	# Should call exit() on old state, enter() on new state,
	# update the state property, and emit state_changed signal
	pass
