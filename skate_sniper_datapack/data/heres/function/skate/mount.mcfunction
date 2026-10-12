tag @s add heres.skating
attribute @s minecraft:movement_speed modifier add heres:skate 0.7 add_multiplied_base
attribute @s minecraft:jump_strength modifier add heres:skate 0.3 add_value
attribute @s minecraft:step_height modifier add heres:skate 0.5 add_value
attribute @s minecraft:safe_fall_distance modifier add heres:skate 10 add_value
playsound minecraft:block.wood.place player @a ~ ~ ~ 1 1.4
title @s actionbar {"text":"На скейте! Пробел — олли","color":"aqua"}
