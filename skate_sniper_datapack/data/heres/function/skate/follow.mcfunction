# Вращение доски (360 шов-ит после прыжка)
scoreboard players remove @s[scores={heres.spin=1..}] heres.spin 45
execute store result storage heres:tmp spin int 1 run scoreboard players get @s heres.spin

scoreboard players operation #id heres.tmp = @s heres.id
scoreboard players set #found heres.tmp 0
execute as @e[type=minecraft:block_display,tag=heres.board] if score @s heres.id = #id heres.tmp run function heres:skate/move with storage heres:tmp
execute if score #found heres.tmp matches 0 run function heres:skate/spawn_board
