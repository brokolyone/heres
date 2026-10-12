package heres.entity;

import heres.HeresMod;
import heres.net.OlliePayload;
import net.minecraft.entity.Entity;
import net.minecraft.entity.EntityType;
import net.minecraft.entity.LivingEntity;
import net.minecraft.entity.MovementType;
import net.minecraft.entity.damage.DamageSource;
import net.minecraft.entity.data.DataTracker;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.item.ItemStack;
import net.minecraft.nbt.NbtCompound;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.sound.SoundCategory;
import net.minecraft.util.ActionResult;
import net.minecraft.util.Hand;
import net.minecraft.util.math.MathHelper;
import net.minecraft.util.math.Vec3d;
import net.minecraft.world.World;
import net.minecraft.world.event.GameEvent;
import org.jetbrains.annotations.Nullable;

/**
 * A rideable skateboard. Like boats, the physics run on whichever side controls it:
 * the rider's client while someone stands on it, the server when it rolls on its own.
 * W pushes, S brakes, A/D carve, space pops an ollie (with a kickflip animation).
 */
public class SkateboardEntity extends Entity {
	/** Height of the grip tape above the ground; the rider's feet go here. */
	public static final double DECK_HEIGHT = 0.085;
	public static final int FLIP_TICKS = 9;
	private static final byte STATUS_OLLIE = 60;

	private static final float MAX_SPEED = 0.55F;
	private static final float PUSH = 0.022F;
	private static final float BRAKE = 0.04F;
	private static final double OLLIE_VELOCITY = 0.52;
	private static final double GRAVITY = 0.08;

	private boolean pressingForward;
	private boolean pressingBack;
	private boolean pressingLeft;
	private boolean pressingRight;
	private boolean pressingJump;
	private boolean wasPressingJump;
	private float speed;
	private float yawVelocity;
	private boolean wasOnGround = true;

	private int lerpTicks;
	private double lerpX;
	private double lerpY;
	private double lerpZ;
	private double lerpYaw;

	/** Client-only kickflip animation countdown. */
	private int flipTicks;

	public SkateboardEntity(EntityType<? extends SkateboardEntity> type, World world) {
		super(type, world);
		this.intersectionChecked = true;
	}

	@Override
	protected void initDataTracker(DataTracker.Builder builder) {
	}

	@Override
	protected void readCustomDataFromNbt(NbtCompound nbt) {
	}

	@Override
	protected void writeCustomDataToNbt(NbtCompound nbt) {
	}

	public void setInputs(boolean forward, boolean back, boolean left, boolean right, boolean jump) {
		this.pressingForward = forward;
		this.pressingBack = back;
		this.pressingLeft = left;
		this.pressingRight = right;
		this.pressingJump = jump;
	}

	@Override
	public void tick() {
		super.tick();
		if (this.flipTicks > 0) {
			this.flipTicks--;
		}
		this.updateLerp();

		if (this.isLogicalSideForUpdatingMovement()) {
			this.simulate();
		} else {
			this.setVelocity(Vec3d.ZERO);
		}
		this.checkBlockCollision();
	}

	private void simulate() {
		Vec3d velocity = this.getVelocity();
		boolean ridden = this.getControllingPassenger() != null;
		boolean onGround = this.isOnGround();
		double vy = onGround ? Math.max(velocity.y, -0.04) : velocity.y;

		if (ridden) {
			float turn = (this.pressingRight ? 1.0F : 0.0F) - (this.pressingLeft ? 1.0F : 0.0F);
			this.yawVelocity += turn * (onGround ? 1.3F : 0.6F);
			if (this.pressingForward && onGround) {
				this.speed = Math.min(MAX_SPEED, this.speed + PUSH);
			}
			if (this.pressingBack && onGround) {
				this.speed = Math.max(0.0F, this.speed - BRAKE);
			}
			if (this.pressingJump && !this.wasPressingJump && onGround) {
				vy = OLLIE_VELOCITY;
				this.startOllie();
			}
			this.wasPressingJump = this.pressingJump;
		} else {
			this.setInputs(false, false, false, false, false);
		}

		this.yawVelocity *= 0.72F;
		this.setYaw(this.getYaw() + this.yawVelocity);
		if (onGround) {
			this.speed *= ridden && this.pressingForward ? 0.997F : 0.985F;
		}
		if (this.speed < 0.004F) {
			this.speed = 0.0F;
		}
		if (this.isTouchingWater()) {
			this.speed *= 0.8F;
		}

		vy = (vy - GRAVITY) * 0.98;
		Vec3d heading = Vec3d.fromPolar(0.0F, this.getYaw());
		this.setVelocity(heading.x * this.speed, vy, heading.z * this.speed);
		this.move(MovementType.SELF, this.getVelocity());

		if (this.horizontalCollision) {
			this.speed *= 0.25F;
		}
		if (this.isOnGround() && !this.wasOnGround && vy < -0.2) {
			this.getWorld().playSound(this.getControllingPassenger() instanceof PlayerEntity p ? p : null,
					this.getX(), this.getY(), this.getZ(), HeresMod.SKATE_LAND, SoundCategory.PLAYERS, 1.0F, 1.0F);
		}
		this.wasOnGround = this.isOnGround();
	}

	private void startOllie() {
		this.flipTicks = FLIP_TICKS;
		World world = this.getWorld();
		if (world.isClient) {
			world.playSound(this.getControllingPassenger() instanceof PlayerEntity p ? p : null,
					this.getX(), this.getY(), this.getZ(), HeresMod.SKATE_POP, SoundCategory.PLAYERS, 1.0F, 1.0F);
			HeresMod.CLIENT_HOOKS.sendToServer(new OlliePayload());
		}
	}

	/** The rider's client did an ollie: tell everyone else to play the trick. */
	public void onRiderOllie(ServerPlayerEntity rider) {
		this.getWorld().playSound(rider, this.getX(), this.getY(), this.getZ(), HeresMod.SKATE_POP, SoundCategory.PLAYERS, 1.0F, 1.0F);
		this.getWorld().sendEntityStatus(this, STATUS_OLLIE);
	}

	@Override
	public void handleStatus(byte status) {
		if (status == STATUS_OLLIE) {
			if (this.flipTicks == 0) {
				this.flipTicks = FLIP_TICKS;
			}
		} else {
			super.handleStatus(status);
		}
	}

	/** 0 → 1 over the kickflip, 0 when not flipping. */
	public float getFlipProgress(float tickDelta) {
		if (this.flipTicks <= 0) {
			return 0.0F;
		}
		return MathHelper.clamp((FLIP_TICKS - this.flipTicks + tickDelta) / FLIP_TICKS, 0.0F, 1.0F);
	}

	private void updateLerp() {
		if (this.isLogicalSideForUpdatingMovement()) {
			this.lerpTicks = 0;
			this.updateTrackedPosition(this.getX(), this.getY(), this.getZ());
		}
		if (this.lerpTicks > 0) {
			this.lerpPosAndRotation(this.lerpTicks, this.lerpX, this.lerpY, this.lerpZ, this.lerpYaw, 0.0);
			this.lerpTicks--;
		}
	}

	@Override
	public void updateTrackedPositionAndAngles(double x, double y, double z, float yaw, float pitch, int interpolationSteps) {
		this.lerpX = x;
		this.lerpY = y;
		this.lerpZ = z;
		this.lerpYaw = yaw;
		this.lerpTicks = 5;
	}

	@Override
	public double getLerpTargetX() {
		return this.lerpTicks > 0 ? this.lerpX : this.getX();
	}

	@Override
	public double getLerpTargetY() {
		return this.lerpTicks > 0 ? this.lerpY : this.getY();
	}

	@Override
	public double getLerpTargetZ() {
		return this.lerpTicks > 0 ? this.lerpZ : this.getZ();
	}

	@Override
	public float getLerpTargetYaw() {
		return this.lerpTicks > 0 ? (float) this.lerpYaw : this.getYaw();
	}

	@Nullable
	@Override
	public LivingEntity getControllingPassenger() {
		return this.getFirstPassenger() instanceof PlayerEntity player ? player : null;
	}

	@Override
	protected boolean canAddPassenger(Entity passenger) {
		return this.getPassengerList().isEmpty();
	}

	@Override
	protected void updatePassengerPosition(Entity passenger, PositionUpdater positionUpdater) {
		positionUpdater.accept(passenger, this.getX(), this.getY() + DECK_HEIGHT, this.getZ());
	}

	@Override
	public ActionResult interact(PlayerEntity player, Hand hand) {
		if (player.shouldCancelInteraction() || this.hasPassengers()) {
			return ActionResult.PASS;
		}
		if (!this.getWorld().isClient) {
			return player.startRiding(this) ? ActionResult.CONSUME : ActionResult.PASS;
		}
		return ActionResult.SUCCESS;
	}

	/** Punch the board to pick it up. */
	@Override
	public boolean damage(DamageSource source, float amount) {
		if (this.getWorld().isClient || this.isRemoved()) {
			return true;
		}
		if (this.isInvulnerableTo(source) || !(source.getAttacker() instanceof PlayerEntity player)) {
			return false;
		}
		if (!player.getAbilities().creativeMode) {
			this.dropStack(new ItemStack(HeresMod.SKATEBOARD));
		}
		this.emitGameEvent(GameEvent.ENTITY_DAMAGE, player);
		this.discard();
		return true;
	}

	@Override
	public boolean handleFallDamage(float fallDistance, float damageMultiplier, DamageSource damageSource) {
		// the board takes the landing; no fall damage for the rider
		return false;
	}

	@Override
	public boolean canHit() {
		return !this.isRemoved();
	}

	@Override
	public float getStepHeight() {
		return 0.6F;
	}

	@Override
	public ItemStack getPickBlockStack() {
		return new ItemStack(HeresMod.SKATEBOARD);
	}

	/** Horizontal speed in blocks per tick, from movement (works on every client). */
	public double getRollingSpeed() {
		double dx = this.getX() - this.prevX;
		double dz = this.getZ() - this.prevZ;
		return Math.sqrt(dx * dx + dz * dz);
	}
}
