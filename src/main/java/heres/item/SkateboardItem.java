package heres.item;

import heres.HeresMod;
import heres.entity.SkateboardEntity;
import java.util.List;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;
import net.minecraft.item.ItemUsageContext;
import net.minecraft.item.tooltip.TooltipType;
import net.minecraft.sound.SoundCategory;
import net.minecraft.sound.SoundEvents;
import net.minecraft.text.Text;
import net.minecraft.util.ActionResult;
import net.minecraft.util.Formatting;
import net.minecraft.util.math.Direction;
import net.minecraft.util.math.Vec3d;
import net.minecraft.world.World;
import net.minecraft.world.event.GameEvent;

/** Right-click a block to put the board down and hop on (sneak to only place it). */
public class SkateboardItem extends Item {
	public SkateboardItem(Settings settings) {
		super(settings);
	}

	@Override
	public ActionResult useOnBlock(ItemUsageContext context) {
		if (context.getSide() == Direction.DOWN) {
			return ActionResult.PASS;
		}
		World world = context.getWorld();
		Vec3d pos = context.getHitPos();
		SkateboardEntity board = new SkateboardEntity(HeresMod.SKATEBOARD_ENTITY, world);
		board.refreshPositionAndAngles(pos.x, pos.y, pos.z, context.getPlayerYaw(), 0.0F);
		if (!world.isSpaceEmpty(board, board.getBoundingBox())) {
			return ActionResult.FAIL;
		}
		if (!world.isClient) {
			world.spawnEntity(board);
			world.emitGameEvent(context.getPlayer(), GameEvent.ENTITY_PLACE, board.getPos());
			world.playSound(null, pos.x, pos.y, pos.z, SoundEvents.BLOCK_WOOD_PLACE, SoundCategory.PLAYERS, 1.0F, 1.3F);
			PlayerEntity player = context.getPlayer();
			if (player != null && !player.isSneaking()) {
				player.startRiding(board);
			}
			context.getStack().decrementUnlessCreative(1, player);
		}
		return ActionResult.success(world.isClient);
	}

	@Override
	public void appendTooltip(ItemStack stack, TooltipContext context, List<Text> tooltip, TooltipType type) {
		tooltip.add(Text.translatable("item.heres.skateboard.tooltip.place").formatted(Formatting.GRAY));
		tooltip.add(Text.translatable("item.heres.skateboard.tooltip.ride").formatted(Formatting.GRAY));
		tooltip.add(Text.translatable("item.heres.skateboard.tooltip.ollie").formatted(Formatting.GRAY));
	}
}
