# Затвор: 1.5 секунды между выстрелами
scoreboard players set @s heres.cd 30

playsound minecraft:entity.generic.explode player @a ~ ~ ~ 1.5 1.8
playsound minecraft:item.crossbow.shoot player @a ~ ~ ~ 2 0.5
playsound minecraft:entity.firework_rocket.blast player @a ~ ~ ~ 2 0.6
execute anchored eyes positioned ^ ^ ^1 run particle minecraft:firework ~ ~ ~ 0.05 0.05 0.05 0.05 6
execute anchored eyes positioned ^ ^ ^1 run particle minecraft:smoke ~ ~ ~ 0.05 0.05 0.05 0.02 8

# Луч (пуля): шаг 0.5 блока, максимум 400 шагов = 200 блоков
tag @s add heres.shooter
scoreboard players set #steps heres.tmp 0
execute anchored eyes positioned ^ ^ ^0.5 run function heres:sniper/ray
tag @s remove heres.shooter

# Отдача
rotate @s ~ ~-4
