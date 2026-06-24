# Copied verbatim from GameDevBench test.gd by import_gamedevbench.py.
# Scored as a SINGLE overall checkpoint via its VALIDATION_PASSED/FAILED
# marker. For per-checkpoint partial credit, rewrite the reporting tail
# to print {"assertions":[...]} (see gdb-task_0002 for an example).
extends Node

func _ready():
    await run_validation()

func fail(msg):
    print("VALIDATION_FAILED: %s" % msg)
    get_tree().quit(1)

func succeed(msg):
    print("VALIDATION_PASSED: %s" % msg)
    get_tree().quit(0)

func ensure(condition, msg):
    if not condition:
        fail(msg)
        return true
    return false

func load_bullet_scene() -> PackedScene:
    var scene: PackedScene = load("res://scenes/entities/tank/weapon/bullet.tscn")
    if ensure(scene != null, "Bullet scene missing at res://scenes/entities/tank/weapon/bullet.tscn"):
        return null
    return scene

func instantiate_bullet(main: Node) -> Area2D:
    var scene = load_bullet_scene()
    if scene == null:
        return null
    var bullet: Area2D = scene.instantiate()
    main.add_child(bullet)
    return bullet

func run_validation() -> void:
    var main: Node = get_node("Main")
    var bullet: Area2D = instantiate_bullet(main)
    if bullet == null:
        return
    var script_ref: Script = bullet.get_script()
    if ensure(script_ref is GDScript, "Bullet must use a GDScript script") or script_ref == null:
        return

    if ensure(has_constant_speed(bullet), "Define const SPEED = 500 in bullet.gd"):
        return
    if ensure(has_script_property(script_ref, "direction"), "Expose a direction property on Bullet"):
        return
    if ensure(has_script_property(script_ref, "tank"), "Expose a tank property on Bullet"):
        return
    if ensure(bullet.has_method("_physics_process"), "Implement _physics_process for bullet movement"):
        return
    if ensure(bullet.has_method("_on_area_entered"), "Implement _on_area_entered handler"):
        return
    if ensure(bullet.has_method("_on_body_entered"), "Implement _on_body_entered handler"):
        return

    if ensure(test_physics_motion(bullet), "_physics_process must move by direction.normalized() * SPEED * delta"):
        return
    if not await test_area_handler(main):
        return
    if not await test_body_handler(main):
        return

    succeed("Bullet script moves forward and cleans up after collisions")

func has_constant_speed(bullet: Area2D) -> bool:
    var script: Script = bullet.get_script()
    if script == null or not (script is GDScript):
        return false
    var constants: Dictionary = (script as GDScript).get_script_constant_map()
    return constants.has("SPEED") and constants["SPEED"] == 500

func has_script_property(script: GDScript, property_name: String) -> bool:
    for prop in script.get_script_property_list():
        if prop.has("name") and prop["name"] == property_name:
            return true
    return false

func test_physics_motion(bullet: Area2D) -> bool:
    bullet.position = Vector2.ZERO
    bullet.direction = Vector2(0, 10)
    bullet._physics_process(0.1)
    return is_equal_approx(bullet.position.length(), 50.0)

func test_area_handler(main: Node) -> bool:
    var temp: Area2D = instantiate_bullet(main)
    if temp == null:
        return false
    if ensure(not temp.is_queued_for_deletion(), "Fresh bullet should be active before collisions"):
        return false
    temp._on_area_entered(null)
    await get_tree().process_frame
    if ensure(not is_instance_valid(temp), "_on_area_entered must queue_free the bullet"):
        return false
    return true

func test_body_handler(main: Node) -> bool:
    var temp: Area2D = instantiate_bullet(main)
    if temp == null:
        return false
    var crate_scene: PackedScene = load("res://scenes/entities/world/crate.tscn")
    if ensure(crate_scene != null, "Crate scene missing for collision test"):
        return false
    var crate: Node = crate_scene.instantiate()
    main.add_child(crate)
    temp._on_body_entered(crate)
    await get_tree().process_frame
    if ensure(not is_instance_valid(temp), "_on_body_entered must queue_free the bullet"):
        return false
    if ensure(not is_instance_valid(crate), "Crate must be destroyed after bullet hit"):
        return false
    return true
