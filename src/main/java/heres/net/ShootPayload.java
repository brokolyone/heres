package heres.net;

import heres.HeresMod;
import net.minecraft.network.RegistryByteBuf;
import net.minecraft.network.codec.PacketCodec;
import net.minecraft.network.codec.PacketCodecs;
import net.minecraft.network.packet.CustomPayload;

/**
 * Client → server: the player pulled the trigger, aiming at yaw/pitch. The aim is
 * sent with the shot because the regular rotation update can arrive a tick late,
 * which made flick shots land where the player was looking before the flick.
 */
public record ShootPayload(float yaw, float pitch) implements CustomPayload {
	public static final CustomPayload.Id<ShootPayload> ID = new CustomPayload.Id<>(HeresMod.id("shoot"));
	public static final PacketCodec<RegistryByteBuf, ShootPayload> CODEC = PacketCodec.tuple(
			PacketCodecs.FLOAT, ShootPayload::yaw,
			PacketCodecs.FLOAT, ShootPayload::pitch,
			ShootPayload::new);

	@Override
	public Id<? extends CustomPayload> getId() {
		return ID;
	}
}
