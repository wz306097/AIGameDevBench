extends Node2D
class_name Tank

var collect_call_count: int = 0
var last_collected = null

func collect(pickup):
    collect_call_count += 1
    last_collected = pickup
