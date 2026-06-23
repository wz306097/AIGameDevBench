extends CharacterBody2D

@export var speed: float = 1200.0
@export var jump_speed: float = -1800.0
@export var gravity: float = 4000.0

func _physics_process(delta: float) -> void:
	velocity.y += gravity * delta
	velocity.x = Input.get_axis("move_left", "move_right") * speed
	move_and_slide()
	if Input.is_action_just_pressed("jump") and is_on_floor():
		velocity.y = jump_speed
