package heres.client.mixin;

import heres.item.SniperRifleItem;
import net.minecraft.entity.player.PlayerEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Aiming the sniper counts as looking through a spyglass: the game then zooms in,
 * slows the mouse, hides the hand and draws the scope overlay (swapped for our reticle).
 */
@Mixin(PlayerEntity.class)
public abstract class PlayerEntityMixin {
	@Inject(method = "isUsingSpyglass", at = @At("HEAD"), cancellable = true)
	private void heres$aimingSniper(CallbackInfoReturnable<Boolean> cir) {
		PlayerEntity self = (PlayerEntity) (Object) this;
		if (self.isUsingItem() && self.getActiveItem().getItem() instanceof SniperRifleItem) {
			cir.setReturnValue(true);
		}
	}
}
