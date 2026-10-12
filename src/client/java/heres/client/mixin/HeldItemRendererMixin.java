package heres.client.mixin;

import heres.client.render.FirstPersonRifle;
import heres.item.SniperRifleItem;
import net.minecraft.client.network.AbstractClientPlayerEntity;
import net.minecraft.client.render.VertexConsumerProvider;
import net.minecraft.client.render.item.HeldItemRenderer;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.item.ItemStack;
import net.minecraft.util.Hand;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** First person: show the sniper held in both of the player's hands. */
@Mixin(HeldItemRenderer.class)
public abstract class HeldItemRendererMixin {
	@Inject(method = "renderFirstPersonItem", at = @At("HEAD"), cancellable = true)
	private void heres$twoHandedRifle(AbstractClientPlayerEntity player, float tickDelta, float pitch, Hand hand,
			float swingProgress, ItemStack item, float equipProgress, MatrixStack matrices,
			VertexConsumerProvider vertexConsumers, int light, CallbackInfo ci) {
		if (!(player.getMainHandStack().getItem() instanceof SniperRifleItem)) {
			return;
		}
		// both hands are on the rifle: draw it once for the main hand, nothing for the off hand
		if (hand == Hand.MAIN_HAND && !player.isUsingSpyglass()) {
			FirstPersonRifle.render(player, item, tickDelta, equipProgress, matrices, vertexConsumers, light);
		}
		ci.cancel();
	}
}
