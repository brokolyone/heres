package heres.client.model;

import heres.HeresMod;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import net.fabricmc.fabric.api.client.model.loading.v1.ModelLoadingPlugin;
import net.fabricmc.fabric.api.client.model.loading.v1.PreparableModelLoadingPlugin;
import net.minecraft.client.texture.SpriteAtlasTexture;
import net.minecraft.client.util.ModelIdentifier;
import net.minecraft.client.util.SpriteIdentifier;
import net.minecraft.resource.Resource;
import net.minecraft.resource.ResourceManager;
import net.minecraft.util.Identifier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Swaps the (empty) JSON item models of the sniper and skateboard for real meshes.
 * The JSON files still provide the display transforms; the geometry comes from
 * assets/heres/meshes/&lt;name&gt;.mesh and the texture from textures/item/&lt;name&gt;.png.
 */
public final class MeshModels {
	private static final Logger LOGGER = LoggerFactory.getLogger("heres");
	private static final List<String> NAMES = List.of("sniper", "skateboard");
	private static volatile Map<String, MeshData> loaded = Map.of();

	private MeshModels() {
	}

	public static void register() {
		PreparableModelLoadingPlugin.register(MeshModels::load, MeshModels::init);
	}

	public static MeshData get(String name) {
		return loaded.get(name);
	}

	private static CompletableFuture<Map<String, MeshData>> load(ResourceManager manager, Executor executor) {
		return CompletableFuture.supplyAsync(() -> {
			Map<String, MeshData> meshes = new HashMap<>();
			for (String name : NAMES) {
				Identifier file = HeresMod.id("meshes/" + name + ".mesh");
				Resource resource = manager.getResource(file).orElse(null);
				if (resource == null) {
					LOGGER.error("Missing mesh {}", file);
					continue;
				}
				try (InputStream in = resource.getInputStream()) {
					meshes.put(name, MeshData.read(in));
				} catch (IOException e) {
					LOGGER.error("Could not read mesh {}", file, e);
				}
			}
			return meshes;
		}, executor);
	}

	private static void init(Map<String, MeshData> meshes, ModelLoadingPlugin.Context context) {
		loaded = Map.copyOf(meshes);
		context.modifyModelAfterBake().register((model, ctx) -> {
			String name = nameOf(ctx.topLevelId(), ctx.resourceId());
			MeshData mesh = name == null ? null : meshes.get(name);
			if (model == null || mesh == null) {
				return model;
			}
			SpriteIdentifier texture = new SpriteIdentifier(SpriteAtlasTexture.BLOCK_ATLAS_TEXTURE, HeresMod.id("item/" + name));
			return new MeshBakedModel(mesh, ctx.textureGetter().apply(texture), model.getTransformation());
		});
	}

	private static String nameOf(ModelIdentifier topLevel, Identifier resource) {
		if (topLevel != null && topLevel.id().getNamespace().equals(HeresMod.MOD_ID) && topLevel.variant().equals("inventory")) {
			return topLevel.id().getPath();
		}
		if (resource != null && resource.getNamespace().equals(HeresMod.MOD_ID) && resource.getPath().startsWith("item/")) {
			return resource.getPath().substring("item/".length());
		}
		return null;
	}
}
