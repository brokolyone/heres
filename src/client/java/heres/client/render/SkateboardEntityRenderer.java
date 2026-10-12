package heres.client.render;

import heres.HeresMod;
import heres.client.model.MeshData;
import heres.client.model.MeshModels;
import heres.entity.SkateboardEntity;
import net.minecraft.client.render.OverlayTexture;
import net.minecraft.client.render.VertexConsumerProvider;
import net.minecraft.client.render.entity.EntityRenderer;
import net.minecraft.client.render.entity.EntityRendererFactory;
import net.minecraft.client.render.item.ItemRenderer;
import net.minecraft.client.render.model.json.ModelTransformationMode;
import net.minecraft.client.texture.SpriteAtlasTexture;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.item.ItemStack;
import net.minecraft.util.Identifier;
import net.minecraft.util.math.MathHelper;
import net.minecraft.util.math.RotationAxis;

/** Draws the skateboard mesh at the entity, spinning it through a kickflip after an ollie. */
public class SkateboardEntityRenderer extends EntityRenderer<SkateboardEntity> {
	private final ItemRenderer itemRenderer;
	private final ItemStack stack = new ItemStack(HeresMod.SKATEBOARD);

	public SkateboardEntityRenderer(EntityRendererFactory.Context context) {
		super(context);
		this.itemRenderer = context.getItemRenderer();
		this.shadowRadius = 0.35F;
	}

	@Override
	public void render(SkateboardEntity board, float yaw, float tickDelta, MatrixStack matrices,
			VertexConsumerProvider vertexConsumers, int light) {
		MeshData mesh = MeshModels.get("skateboard");
		// the mesh is centred on 0.5; item rendering shifts it by -0.5, so lift by the lower half
		float lift = mesh == null ? 0.07F : 0.5F - mesh.minY();
		float half = mesh == null ? 0.07F : (mesh.maxY() - mesh.minY()) / 2;

		matrices.push();
		matrices.multiply(RotationAxis.POSITIVE_Y.rotationDegrees(180.0F - yaw));
		matrices.translate(0.0F, lift, 0.0F);
		float flip = board.getFlipProgress(tickDelta);
		if (flip > 0) {
			// kickflip: roll a full turn around the board's long axis, popping up a little
			matrices.translate(0.0F, MathHelper.sin(flip * MathHelper.PI) * 0.25F, 0.0F);
			matrices.translate(0.0F, half - lift, 0.0F);
			matrices.multiply(RotationAxis.POSITIVE_Z.rotationDegrees(flip * 360.0F));
			matrices.translate(0.0F, lift - half, 0.0F);
		}
		this.itemRenderer.renderItem(this.stack, ModelTransformationMode.NONE, light, OverlayTexture.DEFAULT_UV,
				matrices, vertexConsumers, board.getWorld(), board.getId());
		matrices.pop();
		super.render(board, yaw, tickDelta, matrices, vertexConsumers, light);
	}

	@Override
	public Identifier getTexture(SkateboardEntity entity) {
		return SpriteAtlasTexture.BLOCK_ATLAS_TEXTURE;
	}
}
