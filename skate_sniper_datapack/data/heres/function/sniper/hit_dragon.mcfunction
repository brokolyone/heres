# Дракон уже в анимации смерти (фаза 9) — пуля просто пролетает
execute store result score #phase heres.tmp run data get entity @n[type=minecraft:ender_dragon] DragonPhase
execute if score #phase heres.tmp matches 9 run return 0

# Урон по телу дракона режется в 4 раза (160 → 41 HP), значит хватит 5 попаданий
damage @n[type=minecraft:ender_dragon] 160 minecraft:player_attack by @n[tag=heres.shooter]
particle minecraft:explosion ~ ~ ~ 0.5 0.5 0.5 0 3 force
particle minecraft:damage_indicator ~ ~ ~ 1 1 1 0.2 20 force
playsound minecraft:entity.arrow.hit_player player @a[tag=heres.shooter] ~ ~ ~ 1 0.8

# При смерти игра оставляет дракону 1 HP и включает анимацию смерти
execute store result score #hp heres.tmp run data get entity @n[type=minecraft:ender_dragon] Health
execute if score #hp heres.tmp matches 2.. run title @a[tag=heres.shooter] actionbar [{"text":"+250  ДРАКОН РАНЕН  ","color":"gold","bold":true},{"text":"HP: ","color":"gray","bold":false},{"score":{"name":"#hp","objective":"heres.tmp"},"color":"red","bold":false},{"text":"/200","color":"gray","bold":false}]
execute if score #hp heres.tmp matches ..1 run function heres:sniper/dragon_killed
