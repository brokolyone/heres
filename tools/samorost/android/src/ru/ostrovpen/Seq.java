package ru.ostrovpen;

import java.util.ArrayList;
import java.util.List;

/** A little script of timed steps, advanced by the game ticks (the native stand-in for game.js's async actions). */
final class Seq {
    interface F {
        void k(float k);
    }

    interface Cond {
        boolean ok();
    }

    private abstract static class Step {
        /** Advances by dt ms; true when finished. */
        abstract boolean step(float dt);
    }

    private final List<Step> steps = new ArrayList<>();
    private int i;
    Runnable onDone;

    private static final class Run extends Step {
        final Runnable r;

        Run(Runnable r) {
            this.r = r;
        }

        boolean step(float dt) {
            r.run();
            return true;
        }
    }

    private static final class Delay extends Step {
        float left;

        Delay(float ms) {
            left = ms;
        }

        boolean step(float dt) {
            left -= dt;
            return left <= 0;
        }
    }

    private static final class Tween extends Step {
        final float ms;
        final F f;
        float e = -1;

        Tween(float ms, F f) {
            this.ms = ms;
            this.f = f;
        }

        boolean step(float dt) {
            e = e < 0 ? 0 : e + dt;
            float k = Math.min(1, e / ms);
            f.k(Keys.quad(k));
            return k >= 1;
        }
    }

    private static final class Until extends Step {
        final Cond c;

        Until(Cond c) {
            this.c = c;
        }

        boolean step(float dt) {
            return c.ok();
        }
    }

    Seq run(Runnable r) {
        steps.add(new Run(r));
        return this;
    }

    Seq delay(float ms) {
        steps.add(new Delay(ms));
        return this;
    }

    /** Eased (quadratic in-out) 0..1 over ms. */
    Seq tween(float ms, F f) {
        steps.add(new Tween(ms, f));
        return this;
    }

    Seq until(Cond c) {
        steps.add(new Until(c));
        return this;
    }

    boolean done() {
        return i >= steps.size();
    }

    /** Runs steps until one has to wait; returns true once the whole script has finished. */
    boolean tick(float dt) {
        while (i < steps.size()) {
            if (!steps.get(i).step(dt)) return false;
            i++;
            dt = 0;
        }
        return true;
    }
}
