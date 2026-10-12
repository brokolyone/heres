package heres;

import heres.entity.SkateboardEntity;
import heres.item.SkateboardItem;
import heres.item.SniperRifleItem;
import heres.net.OlliePayload;
import heres.net.ShootPayload;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.itemgroup.v1.ItemGroupEvents;
import net.fabricmc.fabric.api.networking.v1.PayloadTypeRegistry;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.entity.EntityType;
import net.minecraft.entity.SpawnGroup;
import net.minecraft.entity.damage.DamageType;
import net.minecraft.item.Item;
import net.minecraft.item.ItemGroups;
import net.minecraft.network.packet.CustomPayload;
import net.minecraft.registry.Registries;
import net.minecraft.registry.Registry;
import net.minecraft.registry.RegistryKey;
import net.minecraft.registry.RegistryKeys;
import net.minecraft.sound.SoundEvent;
import net.minecraft.util.Identifier;
import net.minecraft.util.Rarity;

public class HeresMod implements ModInitializer {
	public static final String MOD_ID = "heres";

	public static final Item SNIPER = Registry.register(Registries.ITEM, id("sniper"),
			new SniperRifleItem(new Item.Settings().maxCount(1).rarity(Rarity.EPIC)));
	public static final Item SKATEBOARD = Registry.register(Registries.ITEM, id("skateboard"),
			new SkateboardItem(new Item.Settings().maxCount(1)));

	public static final EntityType<SkateboardEntity> SKATEBOARD_ENTITY = Registry.register(Registries.ENTITY_TYPE, id("skateboard"),
			EntityType.Builder.<SkateboardEntity>create(SkateboardEntity::new, SpawnGroup.MISC)
					.dimensions(0.7F, 0.15F)
					.maxTrackingRange(10)
					.build("skateboard"));

	public static final RegistryKey<DamageType> SNIPER_DAMAGE = RegistryKey.of(RegistryKeys.DAMAGE_TYPE, id("sniper"));

	public static final SoundEvent SNIPER_SHOT = sound("sniper.shot");
	public static final SoundEvent SNIPER_BOLT = sound("sniper.bolt");
	public static final SoundEvent SKATE_POP = sound("skateboard.pop");
	public static final SoundEvent SKATE_LAND = sound("skateboard.land");
	public static final SoundEvent SKATE_ROLL = sound("skateboard.roll");

	/** Set by the client entrypoint so common code can send packets without touching client classes. */
	public static ClientHooks CLIENT_HOOKS = payload -> {
	};

	public interface ClientHooks {
		void sendToServer(CustomPayload payload);
	}

	public static Identifier id(String path) {
		return Identifier.of(MOD_ID, path);
	}

	private static SoundEvent sound(String name) {
		Identifier id = id(name);
		return Registry.register(Registries.SOUND_EVENT, id, SoundEvent.of(id));
	}

	@Override
	public void onInitialize() {
		PayloadTypeRegistry.playC2S().register(ShootPayload.ID, ShootPayload.CODEC);
		PayloadTypeRegistry.playC2S().register(OlliePayload.ID, OlliePayload.CODEC);

		ServerPlayNetworking.registerGlobalReceiver(ShootPayload.ID, (payload, context) -> Ballistics.shoot(context.player()));
		ServerPlayNetworking.registerGlobalReceiver(OlliePayload.ID, (payload, context) -> {
			if (context.player().getVehicle() instanceof SkateboardEntity board) {
				board.onRiderOllie(context.player());
			}
		});
		ServerTickEvents.END_SERVER_TICK.register(server -> Ballistics.tick());

		ItemGroupEvents.modifyEntriesEvent(ItemGroups.COMBAT).register(entries -> entries.add(SNIPER));
		ItemGroupEvents.modifyEntriesEvent(ItemGroups.TOOLS).register(entries -> entries.add(SKATEBOARD));
	}
}
