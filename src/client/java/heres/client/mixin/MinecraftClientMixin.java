package heres.client.mixin;

import heres.client.HeresClient;
import heres.item.SniperRifleItem;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.network.ClientPlayerEntity;
import net.minecraft.client.network.ClientPlayerInteractionManager;
import net.minecraft.client.option.GameOptions;
import org.jetbrains.annotations.Nullable;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** With the sniper in hand, left click fires (also while scoped) instead of punching or mining. */
@Mixin(MinecraftClient.class)
public abstract class MinecraftClientMixin {
	@Shadow
	@Nullable
	public ClientPlayerEntity player;

	@Shadow
	@Final
	public GameOptions options;

	@Shadow
	@Nullable
	public ClientPlayerInteractionManager interactionManager;

	@Inject(method = "handleInputEvents", at = @At("HEAD"))
	private void heres$fireSniper(CallbackInfo ci) {
		if (this.player != null && this.player.getMainHandStack().getItem() instanceof SniperRifleItem) {
			while (this.options.attackKey.wasPressed()) {
				HeresClient.tryShoot((MinecraftClient) (Object) this);
			}
		}
	}

	@Inject(method = "handleBlockBreaking", at = @At("HEAD"), cancellable = true)
	private void heres$noMiningWithSniper(boolean breaking, CallbackInfo ci) {
		if (this.player != null && this.player.getMainHandStack().getItem() instanceof SniperRifleItem) {
			if (this.interactionManager != null) {
				this.interactionManager.cancelBlockBreaking();
			}
			ci.cancel();
		}
	}
}
