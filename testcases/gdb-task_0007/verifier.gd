# Copied verbatim from GameDevBench test.gd by import_gamedevbench.py.
# Scored as a SINGLE overall checkpoint via its VALIDATION_PASSED/FAILED
# marker. For per-checkpoint partial credit, rewrite the reporting tail
# to print {"assertions":[...]} (see gdb-task_0002 for an example).
extends Node

var signal_counts: Array[int] = []

func _ready():
	run_validation()

func make_card(id: String, cost: int = 1) -> Card:
	var card = Card.new()
	card.id = id
	card.cost = cost
	return card

func _capture_signal(count: int) -> void:
	signal_counts.append(count)

func ensure(condition: bool, message: String) -> bool:
	if not condition:
		print("VALIDATION_FAILED: %s" % message)
		get_tree().quit(1)
		return true
	return false

func run_validation():
	var card_pile_script: GDScript = load("res://scripts/card_pile.gd")
	var pile = card_pile_script.new() as Resource
	if ensure(pile.cards is Array, "cards export must be an Array"):
		return
	if ensure(pile.empty(), "New CardPile should be empty"):
		return
	pile.card_pile_size_changed.connect(_capture_signal)

	var strike = make_card("strike", 1)
	var defend = make_card("defend", 1)
	pile.add_card(strike)
	pile.add_card(defend)
	if ensure(signal_counts == [1, 2], "Add should emit new counts; got %s" % signal_counts):
		return
	if ensure(pile.cards.size() == 2, "Cards not appended correctly"):
		return

	var drawn = pile.draw_card()
	if ensure(drawn == strike, "draw_card must remove from the front"):
		return
	if ensure(signal_counts[-1] == 1, "draw_card must emit new size after removal"):
		return

	pile.shuffle()
	if ensure(pile.cards.size() == 1 and pile.cards[0] == defend, "shuffle should preserve contents"):
		return

	var bash = make_card("bash", 2)
	pile.add_card(bash)
	var listing = pile._to_string()
	if ensure(listing == "1: defend\n2: bash", "_to_string should enumerate cards, got %s" % listing):
		return

	pile.clear()
	if ensure(signal_counts[-1] == 0, "clear() must emit 0 size"):
		return
	if ensure(pile.empty(), "CardPile should be empty after clear"):
		return
	if ensure(pile.draw_card() == null, "draw_card on empty pile should return null"):
		return

	print("VALIDATION_PASSED: CardPile resource behaves as expected")
	get_tree().quit()
