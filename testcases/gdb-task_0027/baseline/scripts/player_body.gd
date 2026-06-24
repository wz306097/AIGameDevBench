extends Node3D

@export var camera_node: Node3D
@export var camera_actual: Node3D
@export var camera_shake_noise: FastNoiseLite
@export var camera_shake_noise_panning_speed: float = 30.0
@export var camera_shake_max_power: float = 0.15
@export var camera_shake_blend_speed: float = 7.0
@export var camera_shake_return_strength: float = 5.0
@export var camera_shake_noise_strength: float = 0.2
@export var camera_shake_falling_bias: float = 1.0
@export var camera_shake_falling_strength_falloff: float = 2.0
@export var camera_shake_falling_max_strength: float = 1.0
@export var camera_shake_jumping_strength: float = 0.2

var camera_shake_position: Vector3 = Vector3.ZERO
var time_since_started: float = 0.0

func _ready() -> void:
    if camera_actual:
        camera_actual.position = Vector3.ZERO

func _physics_process(delta: float) -> void:
    time_since_started += delta * camera_shake_noise_panning_speed
    if camera_actual == null:
        return

    if camera_shake_position.length() > 0.0001:
        var noise_vector := _sample_noise() * _noise_power_scale()
        camera_actual.position = camera_actual.position.lerp(
            camera_shake_position + noise_vector,
            delta * camera_shake_blend_speed
        )
        camera_shake_position = camera_shake_position.lerp(Vector3.ZERO, delta * camera_shake_return_strength)
    else:
        camera_actual.position = Vector3.ZERO

func impulse_camera(direction: Vector3, power: float) -> void:
    camera_shake_position += direction * power
    camera_shake_position = _clamp_to_max_power(camera_shake_position)

func impulse_camera_with_recoil(direction: Vector3, power: float) -> void:
    impulse_camera(direction, power)
    camera_shake_position += Vector3.UP * camera_shake_jumping_strength
    camera_shake_position = _clamp_to_max_power(camera_shake_position)

func apply_landing_impulse(previous_y_velocity: float) -> void:
    if previous_y_velocity < -camera_shake_falling_bias:
        var fall_strength := inverse_lerp(
            camera_shake_falling_bias,
            camera_shake_falling_bias + camera_shake_falling_strength_falloff,
            abs(previous_y_velocity)
        )
        fall_strength = clamp(fall_strength, 0.0, 1.0)
        impulse_camera(Vector3.DOWN, fall_strength * camera_shake_falling_max_strength)

func _sample_noise() -> Vector3:
    if camera_shake_noise == null:
        return Vector3.ZERO
    return Vector3(
        camera_shake_noise.get_noise_1d(time_since_started),
        camera_shake_noise.get_noise_1d(time_since_started + 1000.0),
        camera_shake_noise.get_noise_1d(time_since_started + 2000.0)
    ) * camera_shake_noise_strength

func _noise_power_scale() -> float:
    var max_power: float = max(camera_shake_max_power, 0.001)
    return clamp(camera_shake_position.length() / max_power, 0.0, 1.0)

func _clamp_to_max_power(value: Vector3) -> Vector3:
    var max_power: float = max(camera_shake_max_power, 0.001)
    if value.length() > max_power:
        return value.normalized() * max_power
    return value

func inverse_lerp(a: float, b: float, value: float) -> float:
    if is_equal_approx(a, b):
        return 0.0
    return (value - a) / (b - a)
