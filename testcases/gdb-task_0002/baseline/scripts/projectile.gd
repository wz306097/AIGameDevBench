extends Area2D

@export var speed := 400.0

# Reference to the QuestManager
var quest_manager

func _ready():
	# Get the QuestManager instance
	quest_manager = get_node("/root/QuestManager")
	if quest_manager == null:
		# If QuestManager is not found in the scene tree, try to load it from addons
		var quest_manager_script = preload("res://addons/quest_manager/QuestManager.gd")
		quest_manager = quest_manager_script.new()
		# Add it to the scene tree if needed
		get_tree().root.add_child(quest_manager)
		quest_manager.name = "QuestManager"

func _physics_process(delta):
	position += Vector2(0, -speed) * delta
	
	# Remove projectile if it goes far off screen (50 pixels above the top)
	if position.y < -50:
		queue_free()

func _on_area_2d_area_entered(area):
	# Check if the area that entered is an enemy
	if area.is_in_group("enemy"):
		# Call QuestManager to progress the kill step
		if quest_manager != null:
			quest_manager.progress_quest("shoot_em_up_quest", "kill")
		# Queue the projectile to free itself after hitting an enemy
		queue_free()
