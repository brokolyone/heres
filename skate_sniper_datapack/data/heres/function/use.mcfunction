execute if items entity @s weapon.mainhand *[minecraft:custom_data~{heres:"sniper"}] run return run function heres:sniper/try_shoot
execute if items entity @s weapon.mainhand *[minecraft:custom_data~{heres:"skateboard"}] run return run function heres:skate/toggle
execute if items entity @s weapon.offhand *[minecraft:custom_data~{heres:"sniper"}] run return run function heres:sniper/try_shoot
execute if items entity @s weapon.offhand *[minecraft:custom_data~{heres:"skateboard"}] run return run function heres:skate/toggle
