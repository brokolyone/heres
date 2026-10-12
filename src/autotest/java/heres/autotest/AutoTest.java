package heres.autotest;

import heres.HeresMod;
import heres.client.HeresClient;
import heres.entity.SkateboardEntity;
import java.util.ArrayList;
import java.util.List;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.ingame.InventoryScreen;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.client.option.Perspective;
import net.minecraft.client.util.ScreenshotRecorder;
import net.minecraft.command.argument.EntityAnchorArgumentType;
import net.minecraft.entity.Entity;
import net.minecraft.entity.EntityType;
import net.minecraft.entity.boss.dragon.EnderDragonEntity;
import net.minecraft.server.integrated.IntegratedServer;
import net.minecraft.server.network.ServerPlayerEntity;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Dev-only scripted playthrough: joins the "test" world, exercises the rifle and the
 * skateboard and saves screenshots to run/screenshots. Logs lines tagged [AUTOTEST].
 */
public class AutoTest implements ClientModInitializer {
	private static final Logger LOG = LoggerFactory.getLogger("heres-autotest");
	private final List<Step> script = new ArrayList<>();
	private int ticksInWorld;
	private int nextAt = 100;
	private int index;

	private record Step(int delay, Runnable action) {
	}

	private void then(int delay, Runnable action) {
		this.script.add(new Step(delay, action));
	}

	@Override
	public void onInitializeClient() {
		MinecraftClient mc = MinecraftClient.getInstance();
		buildScript(mc);
		ClientTickEvents.END_CLIENT_TICK.register(client -> {
			if (client.world == null || client.player == null || this.index >= this.script.size()) {
				return;
			}
			if (++this.ticksInWorld < this.nextAt) {
				return;
			}
			Step step = this.script.get(this.index++);
			try {
				step.action().run();
			} catch (Throwable t) {
				LOG.error("[AUTOTEST] step {} failed", this.index, t);
			}
			if (this.index < this.script.size()) {
				this.nextAt = this.ticksInWorld + this.script.get(this.index).delay();
			}
		});
	}

	private void buildScript(MinecraftClient mc) {
		then(0, () -> {
			cmd(mc, "gamerule doDaylightCycle false");
			cmd(mc, "gamerule doMobSpawning false");
			cmd(mc, "time set 6000");
			cmd(mc, "weather clear");
			cmd(mc, "gamemode creative @a");
			cmd(mc, "tp @a 0.5 -60 0.5 0 0");
			cmd(mc, "item replace entity @a hotbar.0 with heres:sniper");
			cmd(mc, "item replace entity @a hotbar.1 with heres:skateboard");
			cmd(mc, "fill -6 -60 40 6 -50 40 minecraft:stone_bricks");
			mc.player.getInventory().selectedSlot = 0;
			mc.options.setPerspective(Perspective.FIRST_PERSON);
		});
		then(40, () -> shot(mc, "01_firstperson_sniper"));
		then(5, () -> mc.options.setPerspective(Perspective.THIRD_PERSON_FRONT));
		then(20, () -> shot(mc, "02_thirdperson_front_sniper"));
		then(5, () -> mc.options.setPerspective(Perspective.THIRD_PERSON_BACK));
		then(20, () -> shot(mc, "03_thirdperson_back_sniper"));
		// an armor stand uses the same third-person transform and can be viewed side-on
		then(5, () -> {
			mc.options.setPerspective(Perspective.FIRST_PERSON);
			mc.options.hudHidden = true;
			cmd(mc, "summon minecraft:armor_stand 0.5 -60 3.5 {ShowArms:1b,NoBasePlate:1b,Rotation:[90f,0f],"
					+ "Pose:{RightArm:[-90f,0f,0f],LeftArm:[-90f,30f,0f]},HandItems:[{id:\"heres:sniper\",count:1},{}]}");
			cmd(mc, "tp @a 0.5 -59.3 6.2 180 10");
		});
		then(30, () -> shot(mc, "03b_armorstand_side_sniper"));
		if (Boolean.getBoolean("heres.autotest.quick")) {
			then(5, () -> {
				// set the property to only check how the rifle is held
				log("done (quick)");
				mc.scheduleStop();
			});
		}
		then(5, () -> {
			cmd(mc, "kill @e[type=minecraft:armor_stand]");
			cmd(mc, "tp @a 0.5 -60 0.5 0 0");
			mc.options.hudHidden = false;
		});
		then(5, () -> {
			mc.options.setPerspective(Perspective.FIRST_PERSON);
			mc.options.useKey.setPressed(true);
		});
		then(30, () -> {
			log("using spyglass-style scope: " + mc.player.isUsingSpyglass());
			shot(mc, "04_scope");
		});
		then(5, () -> mc.options.useKey.setPressed(false));

		// dragon: five body shots should bring it down
		then(10, () -> cmd(mc, "summon minecraft:ender_dragon 0.5 -54 30 {DragonPhase:10}"));
		for (int i = 1; i <= 5; i++) {
			int n = i;
			then(17, () -> aimAtDragon(mc));
			then(3, () -> KeyBinding.onKeyPressed(KeyBindingHelper.getBoundKeyOf(mc.options.attackKey)));
			then(3, () -> {
				if (n == 1) {
					shot(mc, "05_shot_tracer");
				}
			});
			then(15, () -> log("after shot " + n + ": dragon " + dragonState(mc)));
		}
		then(20, () -> shot(mc, "06_dragon_after_5_shots"));
		then(5, () -> {
			cmd(mc, "kill @e[type=minecraft:ender_dragon]");
			cmd(mc, "fill -6 -60 40 6 -50 40 minecraft:air");
		});

		// skateboard
		then(10, () -> cmd(mc, "summon heres:skateboard 0.5 -60 4 {Rotation:[0f,0f]}"));
		then(10, () -> serverPlayer(mc, (server, sp) -> {
			Entity board = server.getOverworld().getEntitiesByType(HeresMod.SKATEBOARD_ENTITY, e -> true).get(0);
			log("start riding: " + sp.startRiding(board, true));
		}));
		then(10, () -> {
			mc.player.setYaw(0);
			mc.player.setPitch(10);
			mc.options.setPerspective(Perspective.THIRD_PERSON_BACK);
			log("client vehicle: " + mc.player.getVehicle());
		});
		then(20, () -> shot(mc, "07_ride_back"));
		then(5, () -> mc.options.setPerspective(Perspective.THIRD_PERSON_FRONT));
		then(20, () -> shot(mc, "08_ride_front"));
		then(5, () -> {
			mc.options.setPerspective(Perspective.THIRD_PERSON_BACK);
			mc.options.forwardKey.setPressed(true);
		});
		then(30, () -> {
			log("moving: board " + boardInfo(mc));
			shot(mc, "09_moving");
		});
		then(1, () -> mc.options.jumpKey.setPressed(true));
		then(3, () -> {
			log("ollie: board " + boardInfo(mc));
			shot(mc, "10_ollie_a");
		});
		then(3, () -> {
			log("ollie: board " + boardInfo(mc));
			shot(mc, "10_ollie_b");
			mc.options.jumpKey.setPressed(false);
		});
		then(3, () -> shot(mc, "10_ollie_c"));
		then(20, () -> {
			mc.options.forwardKey.setPressed(false);
			log("landed: board " + boardInfo(mc));
		});
		then(40, () -> mc.options.sneakKey.setPressed(true));
		then(5, () -> {
			mc.options.sneakKey.setPressed(false);
			log("after sneak, vehicle: " + mc.player.getVehicle());
		});
		then(20, () -> {
			mc.options.setPerspective(Perspective.FIRST_PERSON);
			mc.options.hudHidden = true;
			cmd(mc, "execute as @a at @e[type=heres:skateboard,limit=1] run tp @s ~1.1 ~0.4 ~1.1 facing entity @e[type=heres:skateboard,limit=1]");
		});
		then(30, () -> shot(mc, "11_board_closeup"));
		then(5, () -> {
			mc.options.hudHidden = false;
			mc.player.getInventory().selectedSlot = 1;
		});
		then(20, () -> shot(mc, "12_skateboard_in_hand"));
		then(5, () -> mc.options.setPerspective(Perspective.THIRD_PERSON_FRONT));
		then(20, () -> shot(mc, "13_skateboard_in_hand_front"));
		then(5, () -> {
			mc.options.setPerspective(Perspective.FIRST_PERSON);
			cmd(mc, "gamemode survival @a");
		});
		then(10, () -> mc.setScreen(new InventoryScreen(mc.player)));
		then(20, () -> shot(mc, "14_inventory"));
		then(5, () -> {
			mc.setScreen(null);
			cmd(mc, "gamemode creative @a");
			cmd(mc, "tp @a 0.5 -60 0.5 0 30");
			cmd(mc, "summon item 0.5 -60 3 {Item:{id:\"heres:sniper\",count:1},PickupDelay:32767}");
			cmd(mc, "summon item 1.5 -60 3 {Item:{id:\"heres:skateboard\",count:1},PickupDelay:32767}");
		});
		then(40, () -> shot(mc, "15_dropped_items"));
		then(10, () -> {
			log("done");
			mc.scheduleStop();
		});
	}

	private static void aimAtDragon(MinecraftClient mc) {
		for (Entity e : mc.world.getEntities()) {
			if (e instanceof EnderDragonEntity dragon) {
				mc.player.lookAt(EntityAnchorArgumentType.EntityAnchor.EYES, dragon.getPos().add(0, 1.5, 0));
			}
		}
	}

	private static String dragonState(MinecraftClient mc) {
		IntegratedServer server = mc.getServer();
		StringBuilder sb = new StringBuilder();
		for (EnderDragonEntity d : server.getOverworld().getEntitiesByType(EntityType.ENDER_DRAGON, e -> true)) {
			sb.append("hp=").append(d.getHealth()).append(" phase=").append(d.getPhaseManager().getCurrent().getType());
		}
		return sb.length() == 0 ? "none" : sb.toString();
	}

	private static String boardInfo(MinecraftClient mc) {
		if (mc.player.getVehicle() instanceof SkateboardEntity b) {
			return String.format("pos=%.2f,%.2f,%.2f speed=%.3f onGround=%s flip=%.2f", b.getX(), b.getY(), b.getZ(),
					b.getRollingSpeed(), b.isOnGround(), b.getFlipProgress(0));
		}
		return "not riding";
	}

	private interface ServerAction {
		void run(IntegratedServer server, ServerPlayerEntity player);
	}

	private static void serverPlayer(MinecraftClient mc, ServerAction action) {
		IntegratedServer server = mc.getServer();
		server.execute(() -> action.run(server, server.getPlayerManager().getPlayerList().get(0)));
	}

	private static void cmd(MinecraftClient mc, String command) {
		IntegratedServer server = mc.getServer();
		server.execute(() -> server.getCommandManager().executeWithPrefix(server.getCommandSource(), command));
	}

	private static void shot(MinecraftClient mc, String name) {
		ScreenshotRecorder.saveScreenshot(mc.runDirectory, name + ".png", mc.getFramebuffer(), text -> log("saved " + name));
	}

	private static void log(String message) {
		LOG.info("[AUTOTEST] {}", message);
	}

	static {
		// referenced so the compile fails loudly if the client entrypoint moves
		HeresClient.class.getName();
	}
}
