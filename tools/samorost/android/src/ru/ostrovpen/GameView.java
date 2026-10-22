package ru.ostrovpen;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.view.Choreographer;
import android.view.MotionEvent;
import android.view.View;

/** Hosts the game: loads it off the main thread, steps it in 40 ms ticks and draws it on a hardware canvas. */
public final class GameView extends View implements Choreographer.FrameCallback {
    private volatile Game game;
    private volatile String error;
    private Sound sound;
    private boolean running;
    private long last;
    private float acc;
    private final Paint msg = new Paint(Paint.ANTI_ALIAS_FLAG);

    public GameView(Context ctx) {
        super(ctx);
        setBackgroundColor(0xff061210);
        msg.setColor(0xb3efe6c8);
        msg.setTextAlign(Paint.Align.CENTER);
        new Thread(() -> {
            try {
                Scene sc = new Scene(ctx.getAssets());
                Sound snd = new Sound(ctx.getAssets(), new String[]{"step_out", "step_in", "boing_m", "creak", "snort", "clock", "sparkle",
                        "musicbox", "whistle", "whoosh", "crackle", "ding", "click", "bloop", "whirr", "buzz", "snore", "yay", "purr"});
                Game g = new Game(ctx.getAssets(), sc, snd);
                post(() -> {
                    sound = snd;
                    game = g;
                    if (!running) snd.pause();
                    invalidate();
                });
            } catch (Throwable e) {
                error = String.valueOf(e);
                postInvalidate();
            }
        }, "load").start();
    }

    /** Ticks without a display (for tests): advance n frames. */
    void step(int n) {
        Game g = game;
        if (g != null) for (int i = 0; i < n; i++) g.tick();
    }

    Game game() {
        return game;
    }

    void resume() {
        running = true;
        last = 0;
        if (sound != null) sound.resume();
        Choreographer.getInstance().postFrameCallback(this);
    }

    void pause() {
        running = false;
        Choreographer.getInstance().removeFrameCallback(this);
        if (sound != null) sound.pause();
    }

    void release() {
        if (sound != null) sound.release();
    }

    @Override
    public void doFrame(long now) {
        if (!running) return;
        if (last != 0) acc += (now - last) / 1e6f;
        last = now;
        Game g = game;
        if (g != null && acc >= Game.FRAME) {
            int steps = Math.min(3, (int) (acc / Game.FRAME));
            acc = Math.min(acc - steps * Game.FRAME, Game.FRAME);
            for (int i = 0; i < steps; i++) g.tick();
            invalidate();
        } else if (g == null) acc = 0;
        Choreographer.getInstance().postFrameCallback(this);
    }

    @Override
    protected void onDraw(Canvas c) {
        Game g = game;
        if (g != null) {
            g.draw(c, getWidth(), getHeight());
            return;
        }
        c.drawColor(0xff061210);
        msg.setTextSize(getHeight() / 18f);
        c.drawText(error != null ? "Не удалось загрузить: " + error : "Остров-пень загружается…", getWidth() / 2f, getHeight() / 2f, msg);
    }

    @Override
    public boolean onTouchEvent(MotionEvent e) {
        Game g = game;
        if (g != null && e.getActionMasked() == MotionEvent.ACTION_DOWN) {
            g.tap(e.getX(), e.getY());
            return true;
        }
        return true;
    }
}
