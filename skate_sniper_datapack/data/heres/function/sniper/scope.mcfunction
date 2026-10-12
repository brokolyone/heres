# Shift со снайперкой в руке = зум (через уменьшение скорости → меньше FOV)
scoreboard players set #scope heres.tmp 0
execute if predicate heres:sneaking if items entity @s weapon.mainhand *[minecraft:custom_data~{heres:"sniper"}] run scoreboard players set #scope heres.tmp 1
execute if score #scope heres.tmp matches 1 unless entity @s[tag=heres.scoped] run function heres:sniper/scope_on
execute if score #scope heres.tmp matches 0 if entity @s[tag=heres.scoped] run function heres:sniper/scope_off
