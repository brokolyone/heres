package heres;

import heres.entity.SkateboardEntity;
import heres.item.SniperRifleItem;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import net.minecraft.block.BlockState;
import net.minecraft.entity.Entity;
import net.minecraft.entity.LivingEntity;
import net.minecraft.entity.boss.dragon.EnderDragonEntity;
import net.minecraft.entity.boss.dragon.EnderDragonPart;
import net.minecraft.entity.damage.DamageSource;
import net.minecraft.entity.projectile.ProjectileUtil;
import net.minecraft.particle.BlockStateParticleEffect;
import net.minecraft.particle.ParticleEffect;
import net.minecraft.particle.ParticleTypes;
import net.minecraft.registry.RegistryKeys;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.server.world.ServerWorld;
import net.minecraft.sound.SoundCategory;
import net.minecraft.sound.SoundEvents;
import net.minecraft.text.Text;
import net.minecraft.util.Formatting;
import net.minecraft.util.hit.BlockHitResult;
import net.minecraft.util.hit.EntityHitResult;
import net.minecraft.util.hit.HitResult;
import net.minecraft.util.math.Box;
import net.minecraft.util.math.MathHelper;
import net.minecraft.util.math.Vec3d;
import net.minecraft.world.RaycastContext;

/** Server side of a shot: hitscan raycast, damage, tracer and hit feedback. */
public final class Ballistics {
	public static final double RANGE = 256.0;
	public static final float DAMAGE = 40.0F;
	/** The dragon divides body hits by 4 (+1), so 160 lands as ~41: five hits to kill. */
	private static final float DRAGON_BODY_DAMAGE = 160.0F;
	/** Head hits are not reduced: a headshot does double. */
	private static final float DRAGON_HEAD_DAMAGE = 80.0F;
	private static final float HEADSHOT_MULTIPLIER = 1.5F;

	private static final List<PendingBolt> PENDING_BOLTS = new ArrayList<>();

	private Ballistics() {
	}

	public static void shoot(ServerPlayerEntity player, float yaw, float pitch) {
		if (!(player.getMainHandStack().getItem() instanceof SniperRifleItem rifle)
				|| player.getItemCooldownManager().isCoolingDown(rifle)
				|| player.isSpectator()) {
			return;
		}
		player.getItemCooldownManager().set(rifle, SniperRifleItem.RELOAD_TICKS);
		ServerWorld world = player.getServerWorld();

		Vec3d eye = player.getEyePos();
		Vec3d dir = Vec3d.fromPolar(MathHelper.clamp(pitch, -90.0F, 90.0F), yaw);
		Vec3d far = eye.add(dir.multiply(RANGE));
		BlockHitResult blockHit = world.raycast(new RaycastContext(eye, far,
				RaycastContext.ShapeType.COLLIDER, RaycastContext.FluidHandling.NONE, player));
		Vec3d end = blockHit.getType() == HitResult.Type.MISS ? far : blockHit.getPos();
		EntityHitResult entityHit = ProjectileUtil.raycast(player, eye, end, new Box(eye, end).expand(1.0),
				e -> e.canHit() && !e.isSpectator() && e != player.getVehicle() && !(e instanceof SkateboardEntity),
				eye.squaredDistanceTo(end));
		Vec3d impact = entityHit != null ? entityHit.getPos() : end;

		world.playSound(null, player.getX(), player.getEyeY(), player.getZ(), HeresMod.SNIPER_SHOT, SoundCategory.PLAYERS, 6.0F,
				0.95F + world.random.nextFloat() * 0.1F);
		PENDING_BOLTS.add(new PendingBolt(player, 12));
		drawTracer(world, player, eye, dir, impact);

		if (entityHit != null) {
			hitEntity(world, player, entityHit.getEntity(), impact);
		} else if (blockHit.getType() == HitResult.Type.BLOCK) {
			BlockState state = world.getBlockState(blockHit.getBlockPos());
			broadcast(world, new BlockStateParticleEffect(ParticleTypes.BLOCK, state), impact, 14, 0.1, 0.15);
			broadcast(world, ParticleTypes.SMOKE, impact, 6, 0.05, 0.02);
			world.playSound(null, impact.x, impact.y, impact.z, state.getSoundGroup().getBreakSound(), SoundCategory.BLOCKS, 1.0F, 1.4F);
		}
	}

	private static void hitEntity(ServerWorld world, ServerPlayerEntity player, Entity target, Vec3d impact) {
		DamageSource source = new DamageSource(
				world.getRegistryManager().get(RegistryKeys.DAMAGE_TYPE).entryOf(HeresMod.SNIPER_DAMAGE), player);
		boolean headshot;
		float damage;
		EnderDragonEntity dragon = null;
		if (target instanceof EnderDragonPart part) {
			dragon = part.owner;
			headshot = part == dragon.head;
			damage = headshot ? DRAGON_HEAD_DAMAGE : DRAGON_BODY_DAMAGE;
		} else {
			headshot = target instanceof LivingEntity living && impact.y > living.getEyeY() - 0.25;
			damage = headshot ? DAMAGE * HEADSHOT_MULTIPLIER : DAMAGE;
		}

		boolean damaged = target.damage(source, damage);
		broadcast(world, ParticleTypes.DAMAGE_INDICATOR, impact, 8, 0.2, 0.2);
		broadcast(world, ParticleTypes.CRIT, impact, 16, 0.1, 0.4);
		if (!damaged) {
			return;
		}
		player.playSoundToPlayer(SoundEvents.ENTITY_ARROW_HIT_PLAYER, SoundCategory.PLAYERS, 0.8F, headshot ? 1.4F : 1.0F);

		if (dragon != null) {
			if (dragon.getHealth() <= 1.0F) {
				Text title = Text.translatable("heres.dragon.killed").formatted(Formatting.GOLD, Formatting.BOLD);
				for (ServerPlayerEntity p : world.getPlayers()) {
					p.sendMessage(Text.translatable("heres.dragon.killed.by", player.getDisplayName()).formatted(Formatting.YELLOW));
				}
				player.sendMessage(title, true);
			} else {
				player.sendMessage(Text.translatable(headshot ? "heres.hit.dragon_head" : "heres.hit.dragon",
						(int) Math.ceil(dragon.getHealth()), (int) dragon.getMaxHealth()).formatted(Formatting.GOLD), true);
			}
		} else if (target instanceof LivingEntity living && living.isDead()) {
			player.sendMessage(Text.translatable(headshot ? "heres.hit.headshot_kill" : "heres.hit.kill").formatted(Formatting.RED), true);
		} else {
			player.sendMessage(Text.translatable(headshot ? "heres.hit.headshot" : "heres.hit").formatted(Formatting.YELLOW), true);
		}
	}

	/** Bright streak from the muzzle to the impact point, visible from far away. */
	private static void drawTracer(ServerWorld world, ServerPlayerEntity shooter, Vec3d eye, Vec3d dir, Vec3d impact) {
		Vec3d right = dir.crossProduct(new Vec3d(0, 1, 0)).normalize();
		Vec3d muzzle = eye.add(dir.multiply(1.2)).add(right.multiply(0.15)).add(0, -0.12, 0);
		Vec3d path = impact.subtract(muzzle);
		double length = path.length();
		Vec3d step = path.normalize();
		for (ServerPlayerEntity viewer : world.getPlayers()) {
			if (viewer.squaredDistanceTo(muzzle) > 320 * 320) {
				continue;
			}
			// the shooter's own view starts the tracer further out so it doesn't fill the scope
			for (double d = viewer == shooter ? 3.0 : 0.0; d < length; d += 0.7) {
				Vec3d p = muzzle.add(step.multiply(d));
				world.spawnParticles(viewer, ParticleTypes.CRIT, true, p.x, p.y, p.z, 1, 0, 0, 0, 0);
			}
			// muzzle flash and smoke would sit right in front of the shooter's own camera
			if (viewer != shooter) {
				world.spawnParticles(viewer, ParticleTypes.FLASH, true, muzzle.x, muzzle.y, muzzle.z, 1, 0, 0, 0, 0);
				world.spawnParticles(viewer, ParticleTypes.SMOKE, true, muzzle.x, muzzle.y, muzzle.z, 5, 0.03, 0.03, 0.03, 0.02);
			}
		}
	}

	private static void broadcast(ServerWorld world, ParticleEffect effect, Vec3d pos, int count, double spread, double speed) {
		for (ServerPlayerEntity viewer : world.getPlayers()) {
			world.spawnParticles(viewer, effect, true, pos.x, pos.y, pos.z, count, spread, spread, spread, speed);
		}
	}

	/** Plays the bolt being cycled a little after the shot. */
	public static void tick() {
		for (Iterator<PendingBolt> it = PENDING_BOLTS.iterator(); it.hasNext(); ) {
			PendingBolt bolt = it.next();
			if (--bolt.ticks > 0) {
				continue;
			}
			it.remove();
			if (!bolt.player.isRemoved()) {
				bolt.player.getServerWorld().playSound(null, bolt.player.getX(), bolt.player.getEyeY(), bolt.player.getZ(),
						HeresMod.SNIPER_BOLT, SoundCategory.PLAYERS, 1.0F, 1.0F);
			}
		}
	}

	private static final class PendingBolt {
		final ServerPlayerEntity player;
		int ticks;

		PendingBolt(ServerPlayerEntity player, int ticks) {
			this.player = player;
			this.ticks = ticks;
		}
	}
}
