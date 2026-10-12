package heres.client;

import heres.HeresMod;
import heres.client.model.MeshModels;
import heres.client.render.SkateboardEntityRenderer;
import heres.client.render.SkateboardRollingSound;
import heres.entity.SkateboardEntity;
import heres.item.SniperRifleItem;
import heres.net.ShootPayload;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientEntityEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.fabricmc.fabric.api.client.rendering.v1.EntityRendererRegistry;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.network.ClientPlayerEntity;
import net.minecraft.client.option.GameOptions;
import net.minecraft.sound.SoundEvents;

public class HeresClient implements ClientModInitializer {
	@Override
	public void onInitializeClient() {
		HeresMod.CLIENT_HOOKS = ClientPlayNetworking::send;
		MeshModels.register();
		EntityRendererRegistry.register(HeresMod.SKATEBOARD_ENTITY, SkateboardEntityRenderer::new);

		ClientEntityEvents.ENTITY_LOAD.register((entity, world) -> {
			if (entity instanceof SkateboardEntity board) {
				MinecraftClient.getInstance().getSoundManager().play(new SkateboardRollingSound(board));
			}
		});
		ClientTickEvents.START_CLIENT_TICK.register(HeresClient::feedSkateboardInput);
	}

	private static void feedSkateboardInput(MinecraftClient client) {
		ClientPlayerEntity player = client.player;
		if (player == null || !(player.getVehicle() instanceof SkateboardEntity board)) {
			return;
		}
		GameOptions o = client.options;
		boolean free = client.currentScreen == null;
		board.setInputs(free && o.forwardKey.isPressed(), free && o.backKey.isPressed(),
				free && o.leftKey.isPressed(), free && o.rightKey.isPressed(), free && o.jumpKey.isPressed());
	}

	/** Called for every left click while the sniper is held. */
	public static void tryShoot(MinecraftClient client) {
		ClientPlayerEntity player = client.player;
		if (player == null || !(player.getMainHandStack().getItem() instanceof SniperRifleItem rifle)) {
			return;
		}
		if (player.getItemCooldownManager().isCoolingDown(rifle)) {
			player.playSound(SoundEvents.BLOCK_DISPENSER_FAIL, 0.4F, 2.0F);
			return;
		}
		ClientPlayNetworking.send(new ShootPayload());
		// predict the server's cooldown so a double click doesn't send twice
		player.getItemCooldownManager().set(rifle, SniperRifleItem.RELOAD_TICKS);
		boolean scoped = player.isUsingSpyglass();
		player.setPitch(player.getPitch() - (scoped ? 2.5F : 5.0F));
		player.setYaw(player.getYaw() + (player.getRandom().nextFloat() - 0.5F) * (scoped ? 1.0F : 2.5F));
	}
}
