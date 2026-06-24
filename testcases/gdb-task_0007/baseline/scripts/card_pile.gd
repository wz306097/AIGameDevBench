class_name CardPile
extends Resource

signal card_pile_size_changed(cards_amount)

@export var cards: Array[Card] = []

func empty() -> bool:
	return false

func draw_card() -> Card:
	return null

func add_card(card: Card) -> void:
	pass

func shuffle() -> void:
	pass

func clear() -> void:
	pass

func _to_string() -> String:
	return ""
