package heres.item;

import java.util.List;
import net.minecraft.block.BlockState;
import net.minecraft.entity.LivingEntity;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;
import net.minecraft.item.tooltip.TooltipType;
import net.minecraft.sound.SoundEvents;
import net.minecraft.text.Text;
import net.minecraft.util.Formatting;
import net.minecraft.util.Hand;
import net.minecraft.util.TypedActionResult;
import net.minecraft.util.UseAction;
import net.minecraft.util.math.BlockPos;
import net.minecraft.world.World;

/**
 * Right mouse (hold) aims down the scope, left mouse fires. Firing is handled by
 * the client sending a ShootPayload; aiming is plain item use, which the client
 * mixins turn into a spyglass-style zoom with a sniper reticle.
 */
public class SniperRifleItem extends Item {
	public static final int RELOAD_TICKS = 30;

	public SniperRifleItem(Settings settings) {
		super(settings);
	}

	@Override
	public TypedActionResult<ItemStack> use(World world, PlayerEntity user, Hand hand) {
		if (hand != Hand.MAIN_HAND) {
			return TypedActionResult.pass(user.getStackInHand(hand));
		}
		user.playSound(SoundEvents.ITEM_SPYGLASS_USE, 1.0F, 0.8F);
		user.setCurrentHand(hand);
		return TypedActionResult.consume(user.getStackInHand(hand));
	}

	@Override
	public void onStoppedUsing(ItemStack stack, World world, LivingEntity user, int remainingUseTicks) {
		user.playSound(SoundEvents.ITEM_SPYGLASS_STOP_USING, 1.0F, 0.8F);
	}

	@Override
	public int getMaxUseTime(ItemStack stack, LivingEntity user) {
		return 72000;
	}

	@Override
	public UseAction getUseAction(ItemStack stack) {
		return UseAction.NONE;
	}

	@Override
	public boolean canMine(BlockState state, World world, BlockPos pos, PlayerEntity miner) {
		return false;
	}

	@Override
	public void appendTooltip(ItemStack stack, TooltipContext context, List<Text> tooltip, TooltipType type) {
		tooltip.add(Text.translatable("item.heres.sniper.tooltip.fire").formatted(Formatting.GRAY));
		tooltip.add(Text.translatable("item.heres.sniper.tooltip.aim").formatted(Formatting.GRAY));
		tooltip.add(Text.translatable("item.heres.sniper.tooltip.damage").formatted(Formatting.DARK_RED));
	}
}
