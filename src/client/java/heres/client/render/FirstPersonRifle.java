package heres.client.render;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.model.ModelPart;
import net.minecraft.client.network.AbstractClientPlayerEntity;
import net.minecraft.client.render.OverlayTexture;
import net.minecraft.client.render.RenderLayer;
import net.minecraft.client.render.VertexConsumerProvider;
import net.minecraft.client.render.entity.PlayerEntityRenderer;
import net.minecraft.client.render.entity.model.PlayerEntityModel;
import net.minecraft.client.render.model.json.ModelTransformationMode;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.item.ItemStack;
import net.minecraft.util.Identifier;
import net.minecraft.util.math.MathHelper;
import net.minecraft.util.math.RotationAxis;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * First-person view of the rifle held in both hands: the right hand on the pistol
 * grip, the left hand under the handguard, the whole rig kicking back on each shot.
 *
 * <p>Everything is laid out in the rifle's own frame (model units, centred on the
 * model), so the hands stay on the rifle when it moves.
 */
public final class FirstPersonRifle {
	/** Where the middle of the rifle sits in view space (camera looks down -Z). */
	private static final Vector3f CENTER = new Vector3f(0.32F, -0.35F, -1.25F);
	private static final float SCALE = 1.2F;
	private static final float ARM_SCALE = 0.6F;

	/** Hand positions on the mesh, relative to its centre (see tools/blender/bake_export.py axes). */
	private static final Vector3f GRIP = new Vector3f(0.0F, -0.085F, 0.31F);
	private static final Vector3f FOREND = new Vector3f(-0.01F, -0.035F, -0.17F);
	/** Direction from each shoulder to its hand, in the rifle frame. */
	private static final Vector3f RIGHT_REACH = new Vector3f(-0.65F, 0.40F, -0.25F).normalize();
	private static final Vector3f LEFT_REACH = new Vector3f(0.45F, 0.35F, -0.80F).normalize();

	private FirstPersonRifle() {
	}

	public static void render(AbstractClientPlayerEntity player, ItemStack stack, float tickDelta, float equipProgress,
			MatrixStack matrices, VertexConsumerProvider vertexConsumers, int light) {
		float kick = recoil(player, stack, tickDelta);

		matrices.push();
		matrices.translate(0.0F, equipProgress * -0.6F, 0.0F);
		matrices.translate(CENTER.x, CENTER.y + 0.03F * kick, CENTER.z + 0.14F * kick);
		matrices.multiply(RotationAxis.POSITIVE_Y.rotationDegrees(3.0F));
		matrices.multiply(RotationAxis.POSITIVE_X.rotationDegrees(7.0F * kick));
		matrices.scale(SCALE, SCALE, SCALE);

		if (!player.isInvisible()) {
			PlayerEntityRenderer renderer = (PlayerEntityRenderer) MinecraftClient.getInstance()
					.getEntityRenderDispatcher().getRenderer(player);
			PlayerEntityModel<AbstractClientPlayerEntity> model = renderer.getModel();
			Identifier skin = player.getSkinTextures().texture();
			renderArm(matrices, vertexConsumers, light, skin, model.rightArm, model.rightSleeve, GRIP, RIGHT_REACH, true);
			renderArm(matrices, vertexConsumers, light, skin, model.leftArm, model.leftSleeve, FOREND, LEFT_REACH, false);
		}

		MinecraftClient.getInstance().getItemRenderer().renderItem(stack, ModelTransformationMode.NONE, light,
				OverlayTexture.DEFAULT_UV, matrices, vertexConsumers, player.getWorld(), player.getId());
		matrices.pop();
	}

	/** 0 at rest, snaps to 1 just after a shot and settles back while the bolt cycles. */
	private static float recoil(AbstractClientPlayerEntity player, ItemStack stack, float tickDelta) {
		float remaining = player.getItemCooldownManager().getCooldownProgress(stack.getItem(), tickDelta);
		if (remaining <= 0.0F) {
			return 0.0F;
		}
		float elapsed = 1.0F - remaining;
		return elapsed < 0.08F ? elapsed / 0.08F : MathHelper.clamp(1.0F - (elapsed - 0.08F) / 0.3F, 0.0F, 1.0F);
	}

	/**
	 * Draws one arm with its hand on {@code hand}, the arm running back along
	 * {@code -reach} toward the (off-screen) shoulder.
	 */
	private static void renderArm(MatrixStack matrices, VertexConsumerProvider vertexConsumers, int light, Identifier skin,
			ModelPart arm, ModelPart sleeve, Vector3f hand, Vector3f reach, boolean right) {
		matrices.push();
		matrices.translate(hand.x, hand.y, hand.z);
		// the arm cuboid hangs along +Y from the shoulder; point +Y along the reach
		matrices.multiply(new Quaternionf().rotationTo(new Vector3f(0, 1, 0), reach));
		// turn the palm toward the rifle
		matrices.multiply(RotationAxis.POSITIVE_Y.rotationDegrees(right ? 90.0F : -90.0F));
		matrices.scale(ARM_SCALE, ARM_SCALE, ARM_SCALE);
		// arm box spans x -3..1 (right) or -1..3 (left), y -2..10 px; put the hand end at the origin
		matrices.translate((right ? 1.0F : -1.0F) / 16.0F, -10.0F / 16.0F, 0.0F);

		drawPart(matrices, vertexConsumers.getBuffer(RenderLayer.getEntitySolid(skin)), light, arm);
		drawPart(matrices, vertexConsumers.getBuffer(RenderLayer.getEntityTranslucent(skin)), light, sleeve);
		matrices.pop();
	}

	private static void drawPart(MatrixStack matrices, net.minecraft.client.render.VertexConsumer consumer, int light, ModelPart part) {
		float px = part.pivotX;
		float py = part.pivotY;
		float pz = part.pivotZ;
		float pitch = part.pitch;
		float yaw = part.yaw;
		float roll = part.roll;
		part.setPivot(0, 0, 0);
		part.setAngles(0, 0, 0);
		part.render(matrices, consumer, light, OverlayTexture.DEFAULT_UV);
		part.setPivot(px, py, pz);
		part.setAngles(pitch, yaw, roll);
	}
}
