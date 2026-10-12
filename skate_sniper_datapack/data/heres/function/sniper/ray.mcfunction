scoreboard players add #steps heres.tmp 1
particle minecraft:crit ~ ~ ~ 0 0 0 0 1 force

# Дракон огромный — ловим его в радиусе 6 блоков от центра
execute if entity @e[type=minecraft:ender_dragon,distance=..6] run return run function heres:sniper/hit_dragon

# Любой другой моб в кубе 1x1x1 вокруг пули
execute positioned ~-0.5 ~-0.5 ~-0.5 if entity @e[type=!#heres:not_target,tag=!heres.shooter,dx=0,dy=0,dz=0] run return run function heres:sniper/hit_mob

# Стена
execute unless block ~ ~ ~ #heres:passable run return run function heres:sniper/hit_block

execute if score #steps heres.tmp matches ..400 positioned ^ ^ ^0.5 run function heres:sniper/ray
