package heres.net;

import heres.HeresMod;
import net.minecraft.network.RegistryByteBuf;
import net.minecraft.network.codec.PacketCodec;
import net.minecraft.network.packet.CustomPayload;

/**
 * Client → server: the rider popped an ollie. Skateboard physics run on the rider's
 * client (like boats), so the server only relays the trick to everyone else.
 */
public record OlliePayload() implements CustomPayload {
	public static final CustomPayload.Id<OlliePayload> ID = new CustomPayload.Id<>(HeresMod.id("ollie"));
	public static final PacketCodec<RegistryByteBuf, OlliePayload> CODEC = PacketCodec.unit(new OlliePayload());

	@Override
	public Id<? extends CustomPayload> getId() {
		return ID;
	}
}
