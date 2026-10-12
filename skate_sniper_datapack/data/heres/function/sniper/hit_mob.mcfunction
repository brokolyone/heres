# Здесь позиция = угол куба 1x1x1 вокруг пули
damage @n[type=!#heres:not_target,tag=!heres.shooter,dx=0,dy=0,dz=0] 40 minecraft:player_attack by @n[tag=heres.shooter]
particle minecraft:damage_indicator ~0.5 ~0.5 ~0.5 0.2 0.2 0.2 0.1 10 force
playsound minecraft:entity.arrow.hit_player player @a[tag=heres.shooter] ~ ~ ~ 1 1
title @a[tag=heres.shooter] actionbar {"text":"+100  ПОПАДАНИЕ","color":"yellow","bold":true}
