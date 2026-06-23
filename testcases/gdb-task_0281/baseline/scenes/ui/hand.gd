extends HBoxContainer

const CARD_UI_SCENE := preload("res://scenes/card_ui/card_ui.tscn")


func add_card(card_title: String) -> void:
	var new_card_ui = CARD_UI_SCENE.instantiate()
	add_child(new_card_ui)
	new_card_ui.home_parent = self
	new_card_ui.card_title = card_title
