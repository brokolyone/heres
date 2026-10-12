# Убираем доску, если её хозяин слез, умер или вышел
scoreboard players operation #id heres.tmp = @s heres.id
scoreboard players set #ok heres.tmp 0
execute as @a[tag=heres.skating] if score @s heres.id = #id heres.tmp run scoreboard players set #ok heres.tmp 1
execute if score #ok heres.tmp matches 0 run kill @s
