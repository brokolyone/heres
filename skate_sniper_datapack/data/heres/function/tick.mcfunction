# Каждому игроку — свой id (чтобы скейт знал хозяина)
execute as @a unless score @s heres.id matches 1.. run function heres:assign_id

# Смерть = слезаем со скейта
execute as @a[scores={heres.death=1..}] run function heres:skate/dismount
scoreboard players reset @a[scores={heres.death=1..}] heres.death

# Использование предметов (ПКМ морковкой на удочке)
execute as @a[scores={heres.use=1..}] at @s run function heres:use
scoreboard players reset @a[scores={heres.use=1..}] heres.use

# Перезарядка снайперки
execute as @a[scores={heres.cd=1}] at @s run function heres:sniper/reloaded
scoreboard players remove @a[scores={heres.cd=1..}] heres.cd 1

# Прицел
execute as @a run function heres:sniper/scope

# Скейт: олли при прыжке
execute as @a[tag=heres.skating,scores={heres.jump=1..}] at @s run function heres:skate/ollie
scoreboard players reset @a[scores={heres.jump=1..}] heres.jump

# Скейт: доска едет под ногами
execute as @a[tag=heres.skating] at @s run function heres:skate/follow
execute as @e[type=minecraft:block_display,tag=heres.board] run function heres:skate/check_owner
