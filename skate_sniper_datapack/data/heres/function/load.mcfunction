# Скоборды
scoreboard objectives add heres.use minecraft.used:minecraft.carrot_on_a_stick
scoreboard objectives add heres.jump minecraft.custom:minecraft.jump
scoreboard objectives add heres.death deathCount
scoreboard objectives add heres.cd dummy
scoreboard objectives add heres.id dummy
scoreboard objectives add heres.spin dummy
scoreboard objectives add heres.tmp dummy

tellraw @a [{"text":"[Скейт & Снайперка] ","color":"gold"},{"text":"загружено! Напиши ","color":"gray"},{"text":"/function heres:give","color":"yellow"},{"text":" чтобы получить снаряжение, и ","color":"gray"},{"text":"/function heres:dragon","color":"yellow"},{"text":" чтобы призвать дракона.","color":"gray"}]
