package heres.client.mixin;

import heres.HeresMod;
import heres.item.SniperRifleItem;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.hud.InGameHud;
import net.minecraft.util.Identifier;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

/** Draws a mil-dot sniper reticle instead of the spyglass ring while aiming the rifle. */
@Mixin(InGameHud.class)
public abstract class InGameHudMixin {
	private static final Identifier SNIPER_SCOPE = HeresMod.id("textures/misc/sniper_scope.png");

	@ModifyArg(method = "renderSpyglassOverlay", index = 0, at = @At(value = "INVOKE",
			target = "Lnet/minecraft/client/gui/DrawContext;drawTexture(Lnet/minecraft/util/Identifier;IIIFFIIII)V"))
	private Identifier heres$sniperReticle(Identifier texture) {
		MinecraftClient client = MinecraftClient.getInstance();
		if (client.player != null && client.player.getActiveItem().getItem() instanceof SniperRifleItem) {
			return SNIPER_SCOPE;
		}
		return texture;
	}
}
