# Copied verbatim from GameDevBench test.gd by import_gamedevbench.py.
# Scored as a SINGLE overall checkpoint via its VALIDATION_PASSED/FAILED
# marker. For per-checkpoint partial credit, rewrite the reporting tail
# to print {"assertions":[...]} (see gdb-task_0002 for an example).
extends Node

var _failed := false

func _ready() -> void:
    run_validation()

func fail(reason: String) -> void:
    if _failed:
        return
    _failed = true
    print("VALIDATION_FAILED: %s" % reason)
    get_tree().quit(1)

func run_validation() -> void:
    var scene: PackedScene = load("res://scenes/main.tscn")
    var root = scene.instantiate()
    add_child(root)
    await get_tree().process_frame

    var player = root.get_node_or_null("PlayerBody")
    var weapon = root.get_node_or_null("WeaponEffects")
    if player == null or weapon == null:
        fail("PlayerBody or WeaponEffects missing from Main scene")
        return

    if not weapon.has_signal("on_shot_camera_impulse"):
        fail("WeaponEffects must declare on_shot_camera_impulse signal")
        return

    if not weapon.has_method("fire_weapon"):
        fail("WeaponEffects must expose fire_weapon()")
        return

    if not player.has_method("apply_weapon_impulse"):
        fail("PlayerBody needs apply_weapon_impulse() handler")
        return

    var connection := Callable(player, "apply_weapon_impulse")
    if not weapon.is_connected("on_shot_camera_impulse", connection):
        fail("Connect WeaponEffects.on_shot_camera_impulse to PlayerBody.apply_weapon_impulse")
        return

    var power_property := weapon.get_property_list().filter(func(info): return info.name == "camera_shake_power")
    if power_property.is_empty():
        fail("camera_shake_power export missing on WeaponEffects")
        return

    if not is_equal_approx(float(weapon.get("camera_shake_power")), 0.3):
        fail("camera_shake_power default must be 0.3")
        return

    var ray_cast = weapon.get_node_or_null("BarrelEnd/BarrelRayCast")
    if ray_cast == null:
        fail("BarrelRayCast missing under WeaponEffects")
        return

    player.camera_shake_position = Vector3.ZERO
    weapon.fire_weapon()
    await get_tree().process_frame

    if player.camera_shake_position.length() <= 0.0:
        fail("apply_weapon_impulse should forward weapon recoil to PlayerBody")
        return

    if player.camera_shake_position.z >= 0.0:
        fail("Impulse direction should push camera backwards along -Z")
        return

    if _failed:
        return
    print("VALIDATION_PASSED: Weapon recoil signal wired into PlayerBody")
    get_tree().quit()
