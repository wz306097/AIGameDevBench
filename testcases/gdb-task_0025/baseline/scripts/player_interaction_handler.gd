extends Area3D
class_name PlayerInteractionHandler

@export var item_types: Array[ItemData] = []
var nearby_bodies: Array[InteractableItem] = []

func _input(event: InputEvent) -> void:
	pass

func pickup_nearest_item() -> void:
	pass

func _on_body_entered(body: Node3D) -> void:
	pass

func _on_body_exited(body: Node3D) -> void:
	pass
