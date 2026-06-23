extends Node2D

@export var quest_name := "Shoot Em Up"
@export var quest_resource: Resource
@onready var quest_progress_label = $UI/QuestProgress

func _ready():
	if quest_resource:
		QuestManager.add_quest(quest_name, quest_resource)
