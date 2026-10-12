# Дека
summon minecraft:block_display ~ ~ ~ {Tags:["heres.board","heres.new"],teleport_duration:1,block_state:{Name:"minecraft:dark_oak_planks"},transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[-0.25f,0.1f,-0.65f],scale:[0.5f,0.06f,1.3f]}}
# Гриптейп
summon minecraft:block_display ~ ~ ~ {Tags:["heres.board","heres.new"],teleport_duration:1,block_state:{Name:"minecraft:black_concrete"},transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[-0.24f,0.16f,-0.6f],scale:[0.48f,0.01f,1.2f]}}
# Колёса
summon minecraft:block_display ~ ~ ~ {Tags:["heres.board","heres.new"],teleport_duration:1,block_state:{Name:"minecraft:yellow_concrete"},transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[-0.25f,0f,0.3f],scale:[0.1f,0.1f,0.1f]}}
summon minecraft:block_display ~ ~ ~ {Tags:["heres.board","heres.new"],teleport_duration:1,block_state:{Name:"minecraft:yellow_concrete"},transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0.15f,0f,0.3f],scale:[0.1f,0.1f,0.1f]}}
summon minecraft:block_display ~ ~ ~ {Tags:["heres.board","heres.new"],teleport_duration:1,block_state:{Name:"minecraft:yellow_concrete"},transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[-0.25f,0f,-0.4f],scale:[0.1f,0.1f,0.1f]}}
summon minecraft:block_display ~ ~ ~ {Tags:["heres.board","heres.new"],teleport_duration:1,block_state:{Name:"minecraft:yellow_concrete"},transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0.15f,0f,-0.4f],scale:[0.1f,0.1f,0.1f]}}
scoreboard players operation @e[type=minecraft:block_display,tag=heres.new] heres.id = #id heres.tmp
execute as @e[type=minecraft:block_display,tag=heres.new] run tp @s ~ ~ ~ facing ^ ^ ^1
tag @e[type=minecraft:block_display,tag=heres.new] remove heres.new
