package heres.net;

import heres.HeresMod;
import net.minecraft.network.RegistryByteBuf;
import net.minecraft.network.codec.PacketCodec;
import net.minecraft.network.packet.CustomPayload;

/** Client → server: the player pulled the trigger. The server does the raycast. */
public record ShootPayload() implements CustomPayload {
	public static final CustomPayload.Id<ShootPayload> ID = new CustomPayload.Id<>(HeresMod.id("shoot"));
	public static final PacketCodec<RegistryByteBuf, ShootPayload> CODEC = PacketCodec.unit(new ShootPayload());

	@Override
	public Id<? extends CustomPayload> getId() {
		return ID;
	}
}
