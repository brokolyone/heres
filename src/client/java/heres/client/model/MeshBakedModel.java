package heres.client.model;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Supplier;
import net.fabricmc.fabric.api.renderer.v1.Renderer;
import net.fabricmc.fabric.api.renderer.v1.RendererAccess;
import net.fabricmc.fabric.api.renderer.v1.mesh.Mesh;
import net.fabricmc.fabric.api.renderer.v1.mesh.MeshBuilder;
import net.fabricmc.fabric.api.renderer.v1.mesh.MutableQuadView;
import net.fabricmc.fabric.api.renderer.v1.mesh.QuadEmitter;
import net.fabricmc.fabric.api.renderer.v1.model.FabricBakedModel;
import net.fabricmc.fabric.api.renderer.v1.render.RenderContext;
import net.minecraft.block.BlockState;
import net.minecraft.client.render.model.BakedModel;
import net.minecraft.client.render.model.BakedQuad;
import net.minecraft.client.render.model.json.ModelOverrideList;
import net.minecraft.client.render.model.json.ModelTransformation;
import net.minecraft.client.texture.Sprite;
import net.minecraft.item.ItemStack;
import net.minecraft.util.math.BlockPos;
import net.minecraft.util.math.Direction;
import net.minecraft.util.math.random.Random;
import net.minecraft.world.BlockRenderView;
import org.jetbrains.annotations.Nullable;

/**
 * Renders a full triangle mesh (not just Minecraft's cuboids). Each triangle becomes a
 * quad with its last vertex doubled, and carries per-vertex normals so curved parts
 * (barrel, scope, wheels) are shaded smoothly by the Fabric renderer.
 */
public class MeshBakedModel implements BakedModel, FabricBakedModel {
	private final Mesh mesh;
	private final List<BakedQuad> vanillaQuads;
	private final Sprite sprite;
	private final ModelTransformation transformation;

	public MeshBakedModel(MeshData data, Sprite sprite, ModelTransformation transformation) {
		this.sprite = sprite;
		this.transformation = transformation;
		this.mesh = buildMesh(data, sprite);
		this.vanillaQuads = buildVanillaQuads(data, sprite);
	}

	private static Mesh buildMesh(MeshData data, Sprite sprite) {
		Renderer renderer = RendererAccess.INSTANCE.getRenderer();
		if (renderer == null) {
			return null;
		}
		MeshBuilder builder = renderer.meshBuilder();
		QuadEmitter emitter = builder.getEmitter();
		float[] v = data.vertices();
		int stride = MeshData.FLOATS_PER_VERTEX;
		for (int tri = 0; tri < data.triangles(); tri++) {
			for (int corner = 0; corner < 4; corner++) {
				int o = (tri * 3 + Math.min(corner, 2)) * stride;
				emitter.pos(corner, v[o], v[o + 1], v[o + 2]);
				emitter.uv(corner, v[o + 3], v[o + 4]);
				emitter.normal(corner, v[o + 5], v[o + 6], v[o + 7]);
				emitter.color(corner, -1);
			}
			emitter.spriteBake(sprite, MutableQuadView.BAKE_NORMALIZED);
			emitter.nominalFace(faceOf(v, tri * 3 * stride));
			emitter.cullFace(null);
			emitter.emit();
		}
		return builder.build();
	}

	/** Fallback for renderers without the Fabric rendering API (flat, per-face lighting). */
	private static List<BakedQuad> buildVanillaQuads(MeshData data, Sprite sprite) {
		float[] v = data.vertices();
		int stride = MeshData.FLOATS_PER_VERTEX;
		List<BakedQuad> quads = new ArrayList<>(data.triangles());
		for (int tri = 0; tri < data.triangles(); tri++) {
			int[] packed = new int[32];
			for (int corner = 0; corner < 4; corner++) {
				int o = (tri * 3 + Math.min(corner, 2)) * stride;
				int p = corner * 8;
				packed[p] = Float.floatToRawIntBits(v[o]);
				packed[p + 1] = Float.floatToRawIntBits(v[o + 1]);
				packed[p + 2] = Float.floatToRawIntBits(v[o + 2]);
				packed[p + 3] = -1;
				packed[p + 4] = Float.floatToRawIntBits(sprite.getFrameU(v[o + 3]));
				packed[p + 5] = Float.floatToRawIntBits(sprite.getFrameV(v[o + 4]));
			}
			quads.add(new BakedQuad(packed, -1, faceOf(v, tri * 3 * stride), sprite, true));
		}
		return quads;
	}

	/** Axis direction closest to the triangle's averaged vertex normal. */
	private static Direction faceOf(float[] v, int offset) {
		int stride = MeshData.FLOATS_PER_VERTEX;
		float nx = 0;
		float ny = 0;
		float nz = 0;
		for (int i = 0; i < 3; i++) {
			nx += v[offset + i * stride + 5];
			ny += v[offset + i * stride + 6];
			nz += v[offset + i * stride + 7];
		}
		return Direction.getFacing(nx, ny, nz);
	}

	@Override
	public boolean isVanillaAdapter() {
		return this.mesh == null;
	}

	@Override
	public void emitItemQuads(ItemStack stack, Supplier<Random> randomSupplier, RenderContext context) {
		this.mesh.outputTo(context.getEmitter());
	}

	@Override
	public void emitBlockQuads(BlockRenderView blockView, BlockState state, BlockPos pos, Supplier<Random> randomSupplier,
			RenderContext context) {
		this.mesh.outputTo(context.getEmitter());
	}

	@Override
	public List<BakedQuad> getQuads(@Nullable BlockState state, @Nullable Direction face, Random random) {
		return face == null ? this.vanillaQuads : List.of();
	}

	@Override
	public boolean useAmbientOcclusion() {
		return false;
	}

	@Override
	public boolean hasDepth() {
		return true;
	}

	@Override
	public boolean isSideLit() {
		return true;
	}

	@Override
	public boolean isBuiltin() {
		return false;
	}

	@Override
	public Sprite getParticleSprite() {
		return this.sprite;
	}

	@Override
	public ModelTransformation getTransformation() {
		return this.transformation;
	}

	@Override
	public ModelOverrideList getOverrides() {
		return ModelOverrideList.EMPTY;
	}
}
