# Converted from GameDevBench task_0002 scripts/test.gd.
# Same checks as the golden verifier, but emits one assertion per requirement
# so AIGameDevBench scores per-checkpoint instead of overall pass/fail.
# Runs in SCENE mode (extends Node) so the QuestManager autoload is available.
extends Node

func _ready():
	run_validation()

func run_validation():
	var checks = []
	var qm = _get_qm()
	qm.wipe_player_data()
	var quest_res = load("res://quests/shoot_em_up_quest.tres")
	qm.add_quest("Shoot Em Up", quest_res)
	var projectile_scene = load("res://scenes/projectile.tscn")

	# Checkpoint 1: removes itself when far off screen
	var projectile = projectile_scene.instantiate()
	add_child(projectile)
	projectile.position.y = -80
	projectile._physics_process(0.016)
	checks.append({
		"name": "offscreen_removal",
		"pass": projectile.is_queued_for_deletion(),
		"detail": "projectile should queue_free when leaving the play area",
	})

	# Checkpoint 2: reacts to enemies via _on_area_entered
	var enemy = Area2D.new()
	enemy.add_to_group("enemy")
	add_child(enemy)
	var quest = qm.get_player_quest("Shoot Em Up")
	var before = quest.quest_steps[quest.first_step].collected
	projectile = projectile_scene.instantiate()
	add_child(projectile)
	var has_handler = projectile.has_method("_on_area_entered")
	checks.append({
		"name": "has_on_area_entered",
		"pass": has_handler,
		"detail": "projectile must define _on_area_entered to react to enemies",
	})

	# Checkpoints 3 & 4 depend on the handler existing.
	var step_pass = false
	var hit_removal_pass = false
	if has_handler:
		projectile._on_area_entered(enemy)
		var after = qm.get_player_quest("Shoot Em Up").quest_steps[quest.first_step].collected
		step_pass = after == before + 1
		hit_removal_pass = projectile.is_queued_for_deletion()
	checks.append({
		"name": "kill_step_increment",
		"pass": step_pass,
		"detail": "colliding with an enemy must advance the kill step by exactly 1",
	})
	checks.append({
		"name": "self_removal_on_hit",
		"pass": hit_removal_pass,
		"detail": "projectile must queue_free after damaging an enemy",
	})

	# Checkpoint 5: UI label present for visual feedback
	var main_scene = load("res://scenes/main.tscn")
	var main = main_scene.instantiate()
	var ui = main.get_node_or_null("UI")
	var label = null
	if ui:
		label = ui.get_node_or_null("QuestProgress")
	checks.append({
		"name": "ui_quest_progress_label",
		"pass": label != null and label is Label,
		"detail": "Main/UI must contain a QuestProgress Label for progress display",
	})
	main.free()

	qm.wipe_player_data()
	print(JSON.stringify({"assertions": checks}))
	get_tree().quit()

func _get_qm():
	return get_tree().root.get_node("QuestManager")
