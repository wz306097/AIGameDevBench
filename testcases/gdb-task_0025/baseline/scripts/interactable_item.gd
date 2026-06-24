extends Node3D
class_name InteractableItem

@export var item_highlight_mesh: MeshInstance3D

func _ready() -> void:
	# Ensure the highlight stays hidden until focus is gained.
	if item_highlight_mesh:
		item_highlight_mesh.visible = false

func gain_focus() -> void:
	if not item_highlight_mesh:
		push_warning("Interactable item is missing its highlight mesh.")
		return
	item_highlight_mesh.visible = true

func lose_focus() -> void:
	if not item_highlight_mesh:
		return
	item_highlight_mesh.visible = false
