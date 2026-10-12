package heres.client.mixin;

import heres.item.SniperRifleItem;
import net.minecraft.client.network.AbstractClientPlayerEntity;
import net.minecraft.client.render.entity.PlayerEntityRenderer;
import net.minecraft.client.render.entity.model.BipedEntityModel;
import net.minecraft.util.Hand;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Hold the rifle shouldered with both hands (the charged-crossbow pose). */
@Mixin(PlayerEntityRenderer.class)
public abstract class PlayerEntityRendererMixin {
	@Inject(method = "getArmPose", at = @At("HEAD"), cancellable = true)
	private static void heres$rifleHold(AbstractClientPlayerEntity player, Hand hand,
			CallbackInfoReturnable<BipedEntityModel.ArmPose> cir) {
		if (hand == Hand.MAIN_HAND && player.getStackInHand(hand).getItem() instanceof SniperRifleItem) {
			cir.setReturnValue(BipedEntityModel.ArmPose.CROSSBOW_HOLD);
		}
	}
}
