package heres.client.render;

import heres.HeresMod;
import heres.entity.SkateboardEntity;
import net.minecraft.client.sound.MovingSoundInstance;
import net.minecraft.client.sound.SoundInstance;
import net.minecraft.sound.SoundCategory;
import net.minecraft.util.math.MathHelper;

/** Looping wheel rumble that follows a board, louder and higher the faster it rolls. */
public class SkateboardRollingSound extends MovingSoundInstance {
	private final SkateboardEntity board;

	public SkateboardRollingSound(SkateboardEntity board) {
		super(HeresMod.SKATE_ROLL, SoundCategory.NEUTRAL, SoundInstance.createRandom());
		this.board = board;
		this.repeat = true;
		this.repeatDelay = 0;
		this.volume = 0.0F;
		this.x = board.getX();
		this.y = board.getY();
		this.z = board.getZ();
	}

	@Override
	public boolean shouldAlwaysPlay() {
		return true;
	}

	@Override
	public void tick() {
		if (this.board.isRemoved()) {
			this.setDone();
			return;
		}
		this.x = this.board.getX();
		this.y = this.board.getY();
		this.z = this.board.getZ();
		double speed = this.board.isOnGround() ? this.board.getRollingSpeed() : 0.0;
		float target = (float) MathHelper.clamp(speed * 2.2, 0.0, 0.9);
		this.volume = MathHelper.lerp(0.3F, this.volume, target);
		this.pitch = 0.7F + (float) MathHelper.clamp(speed, 0.0, 0.6);
	}
}
