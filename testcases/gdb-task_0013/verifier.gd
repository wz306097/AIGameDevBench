# Copied verbatim from GameDevBench test.gd by import_gamedevbench.py.
# Scored as a SINGLE overall checkpoint via its VALIDATION_PASSED/FAILED
# marker. For per-checkpoint partial credit, rewrite the reporting tail
# to print {"assertions":[...]} (see gdb-task_0002 for an example).
extends Node

class DummyState:
    extends State
    var entered := false
    var exited := false
    func _init(actor: Node) -> void:
        super(actor)
    func enter() -> void:
        entered = true
    func exit() -> void:
        exited = true

func _ready() -> void:
    load("res://components/state.gd")
    load("res://components/finite_state_machine.gd")
    run_validation()

func _fail(message: String) -> void:
    print("VALIDATION_FAILED: %s" % message)
    get_tree().quit(1)

func _succeed() -> void:
    print("VALIDATION_PASSED: FSM foundations implemented")
    get_tree().quit(0)

func _ensure(condition: bool, message: String) -> bool:
    if not condition:
        _fail(message)
        return true
    return false

func run_validation() -> void:
    var actor := Node.new()
    var state := State.new(actor)
    if _ensure(state.actor == actor, "State must stash the actor passed to _init"):
        return

    var fsm := FiniteStateMachine.new()
    if _ensure(fsm.has_signal("state_changed"), "FiniteStateMachine needs a state_changed signal"):
        return

    var first := DummyState.new(actor)
    var second := DummyState.new(actor)
    var signals := []
    fsm.state_changed.connect(func(new_state: State): signals.append(new_state))

    fsm.change_state(first)
    if _ensure(fsm.state == first, "change_state must update the active state"):
        return
    if _ensure(first.entered, "change_state should call enter() on the new state"):
        return

    fsm.change_state(second)
    if _ensure(first.exited, "change_state should call exit() on the outgoing state"):
        return
    if _ensure(second.entered, "change_state must enter the replacement state"):
        return
    if _ensure(signals.size() == 2, "state_changed must emit for every transition"):
        return

    _succeed()
