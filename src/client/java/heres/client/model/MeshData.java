package heres.client.model;

import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * A triangle mesh exported by tools/blender/bake_export.py.
 *
 * <p>Format (little endian): "HMSH", int32 triangle count, then per vertex
 * x, y, z, u, v, nx, ny, nz as float32. Positions are in model space (one block
 * = 1.0, centred on 0.5), UVs are 0..1 in the model's own baked texture.
 */
public record MeshData(float[] vertices, int triangles, float minY, float maxY) {
	public static final int FLOATS_PER_VERTEX = 8;

	public static MeshData read(InputStream in) throws IOException {
		ByteBuffer buf = ByteBuffer.wrap(in.readAllBytes()).order(ByteOrder.LITTLE_ENDIAN);
		if (buf.get() != 'H' || buf.get() != 'M' || buf.get() != 'S' || buf.get() != 'H') {
			throw new IOException("not a HMSH mesh");
		}
		int triangles = buf.getInt();
		float[] vertices = new float[triangles * 3 * FLOATS_PER_VERTEX];
		buf.asFloatBuffer().get(vertices);
		float minY = Float.MAX_VALUE;
		float maxY = -Float.MAX_VALUE;
		for (int i = 1; i < vertices.length; i += FLOATS_PER_VERTEX) {
			minY = Math.min(minY, vertices[i]);
			maxY = Math.max(maxY, vertices[i]);
		}
		return new MeshData(vertices, triangles, minY, maxY);
	}
}
