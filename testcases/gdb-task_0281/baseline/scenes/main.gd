extends Node2D

@onready var hand := $HUD/CardRow


func _ready() -> void:
	hand.add_card("Guard")
	hand.add_card("Brace")
	hand.add_card("Cleave")
