package ru.ostrovpen;

import android.content.res.AssetManager;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.LinearGradient;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.os.Build;
import android.text.Layout;
import android.text.StaticLayout;
import android.text.TextPaint;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Random;
import java.util.Set;

/**
 * «Остров-пень», the native port of game.js: the jointed gnome, walking, the hotspots and their little
 * shows, the door into the house, discoveries, the interface, all advanced in 25 fps ticks.
 */
final class Game {
    static final float FRAME = 40;  // ms: 25 frames a second, on purpose, for a stop-motion feel

    private final Scene sc;
    private final Sound snd;
    private final Random rnd = new Random();

    // ---------------- ground under the gnome ----------------
    private static final float[][] SEGS = {{380, 610, 470, 560, 600, 545, 720, 548}, {720, 548, 850, 550, 980, 555, 1080, 570},
            {1080, 570, 1150, 580, 1200, 595, 1230, 615}};
    private final float[][] gt;

    private float groundY(float x) {
        for (int i = 1; i < gt.length; i++)
            if (gt[i][0] >= x) {
                float x0 = gt[i - 1][0], y0 = gt[i - 1][1], x1 = gt[i][0], y1 = gt[i][1];
                return y0 + (y1 - y0) * (x - x0) / Math.max(1e-6f, x1 - x0);
            }
        return gt[gt.length - 1][1];
    }

    private boolean in() {
        return inside;
    }

    private float minX() {
        return in() ? 175 : 430;
    }

    private float maxX() {
        return in() ? 1430 : 1085;
    }

    private float feet(float x) {
        return in() ? 905 : groundY(x) - .5f;
    }

    private float scale() {
        return in() ? 2.3f : 1;
    }

    private float speed() {
        return in() ? 230 : 105;
    }

    private float stride() {
        return in() ? 8.4f : 3.6f;
    }

    // ---------------- the gnome ----------------
    private static final String[] LIMBS = {"shadow", "beam", "legL", "legR", "body", "armL", "armR", "head", "eyes"};
    private static final int SHADOW = 0, BEAM = 1, LEGL = 2, LEGR = 3, BODY = 4, ARML = 5, ARMR = 6, HEAD = 7, EYES = 8;
    private final Bitmap[] limb = new Bitmap[LIMBS.length];
    private final RectF[] limbBox = new RectF[LIMBS.length];

    boolean inside;
    float x = 780, dir = 1, walk, phase, arm, armL, look, blink = 1, beam = 1, fade = 1, lookTo;
    float target = Float.NaN;
    private float nextBlink = 2, nextLook = 5, t;
    private int lastStep;
    boolean busy, sleeping;
    private Spot action;

    // ---------------- scripts, tweens, effects ----------------
    private final List<Seq> seqs = new ArrayList<>();

    private static final class Particle {
        String kind, text;
        boolean in;
        float x, y, dur, delay, t;
        Keys k;
    }

    private final List<Particle> fx = new ArrayList<>();

    // ---------------- interface ----------------
    boolean started, loaded;
    private float startA = 1, foundA, toastA, toastLeft, curtain, curtainTo;
    private String toast = "";
    private final Set<String> found = new HashSet<>();
    private int total;
    private final Typeface font;
    private final TextPaint text = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final Paint ui = new Paint(Paint.ANTI_ALIAS_FLAG), bmp = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final Paint dotP, sparkP, puffP, streakP;
    private final Matrix m = new Matrix();
    private final float[] s = new float[Keys.N];
    private final RectF r = new RectF();
    // screen layout (px), set by draw()
    private float vw, vh, k, ox, oy, u;
    private final RectF playBtn = new RectF(), sndBtn = new RectF();

    Game(AssetManager am, Scene scene, Sound sound) throws Exception {
        sc = scene;
        snd = sound;
        List<float[]> pts = new ArrayList<>();
        for (float[] sg : SEGS)
            for (int i = 0; i <= 100; i++) {
                float q = i / 100f, w = 1 - q;
                float b0 = w * w * w, b1 = 3 * w * w * q, b2 = 3 * w * q * q, b3 = q * q * q;
                pts.add(new float[]{b0 * sg[0] + b1 * sg[2] + b2 * sg[4] + b3 * sg[6], b0 * sg[1] + b1 * sg[3] + b2 * sg[5] + b3 * sg[7]});
            }
        java.util.Collections.sort(pts, (a, b) -> Float.compare(a[0], b[0]));
        gt = pts.toArray(new float[0][]);

        JSONObject boxes = new JSONObject(Scene.read(am, "scene.json")).getJSONObject("hero").getJSONObject("boxes");
        for (int i = 0; i < LIMBS.length; i++) {
            limb[i] = Scene.bitmap(am, "hero/" + LIMBS[i] + ".png");
            org.json.JSONArray b = boxes.getJSONArray(LIMBS[i]);
            limbBox[i] = new RectF((float) b.getDouble(0), (float) b.getDouble(1),
                    (float) (b.getDouble(0) + b.getDouble(2)), (float) (b.getDouble(1) + b.getDouble(3)));
        }
        Typeface f;
        try {
            f = Typeface.createFromAsset(am, "font.ttf");
        } catch (Exception e) {
            f = Typeface.SERIF;
        }
        font = f;
        text.setTypeface(font);
        dotP = glow(3, 0xfff6e6a0, 14, .6f, 0xf6e6a0);
        sparkP = glow(2, 0xffffd27a, 10, .8f, 0xffaa3c);
        puffP = new Paint(Paint.ANTI_ALIAS_FLAG);
        puffP.setShader(new RadialGradient(0, 0, 1, new int[]{0xb3dcdacd, 0x00dcdacd}, new float[]{0, .7f}, Shader.TileMode.CLAMP));
        streakP = new Paint(Paint.ANTI_ALIAS_FLAG);
        streakP.setShader(new LinearGradient(0, 0, 120, 0, 0x00fffae1, 0xf2fffae1, Shader.TileMode.CLAMP));
        doorFrame(0);
        buildSpots();
        Set<String> keys = new HashSet<>();
        for (Spot sp : spots) keys.add(sp.key);
        keys.add("mushrooms");
        total = keys.size();
        loaded = true;
    }

    private static Paint glow(float core, int coreColor, float outer, float a, int rgb) {
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        int g = rgb & 0xffffff;
        p.setShader(new RadialGradient(0, 0, 1, new int[]{coreColor, coreColor, (Math.round(a * 255) << 24) | g, (Math.round(a * 100) << 24) | g, g},
                new float[]{0, core / outer, (core + .8f) / outer, .55f, 1}, Shader.TileMode.CLAMP));
        return p;
    }

    // ---------------- sound effects ----------------
    private void sfx(String n) {
        snd.play(n);
    }

    private void boing(float size) {
        snd.play("boing_m", 1, 1.2f / Math.max(.5f, size));
    }

    // ---------------- helpers for the shows ----------------
    private Scene.Part part(String id) {
        return sc.parts.get(id);
    }

    private static Keys waapi(int ease) {
        return new Keys(ease, false);
    }

    /** A Web-Animations-style one-shot on a sprite's image, origin as fractions of its box. */
    private void poke(String id, Keys k, float ms, float fx, float fy) {
        Scene.Part p = part(id);
        if (p == null) return;
        p.poke = new Scene.Fx(k, ms, p.box.left + p.box.width() * fx, p.box.top + p.box.height() * fy);
    }

    private void flash(String id, Keys k, float ms) {
        Scene.Part p = part(id);
        if (p == null) return;
        p.flash = new Scene.Fx(k, ms, p.ox, p.oy);
    }

    private Keys bright(float peak) {
        return waapi(Keys.LINEAR).k(-1, "br", 1).k(-1, "br", peak).k(-1, "br", 1).done();
    }

    private void speed(String[] ids, float rate, float ms) {
        for (String id : ids) {
            Scene.Part p = part(id);
            if (p == null) continue;
            p.rate = rate;
            p.rateLeft = ms;
        }
    }

    private void flyOff(String id, float[][] path, float ms, boolean spin) {
        Scene.Part p = part(id);
        if (p == null) return;
        Keys k = waapi(Keys.EASE_IN_OUT);
        for (int i = 0; i < path.length; i++)
            k.k(-1, "tx", path[i][0], "ty", path[i][1], "rot", spin ? i / (float) (path.length - 1) * 360 : 0);
        p.fly = new Scene.Fx(k.done(), ms, p.box.centerX(), p.box.centerY());
    }

    private void particle(String kind, float x, float y, Keys k, float ms, float delay, String txt) {
        Particle p = new Particle();
        p.kind = kind;
        p.x = x;
        p.y = y;
        p.k = k;
        p.dur = ms;
        p.delay = delay;
        p.text = txt;
        p.in = inside;
        fx.add(p);
    }

    private float rand() {
        return rnd.nextFloat();
    }

    /** Raise the lamp arm, hold, and let it drop back while the show goes on. */
    private Seq reach(Seq q, float up, float ms, float hold) {
        return q.tween(ms, kk -> arm = up * kk).delay(hold).run(() -> play(new Seq().tween(ms, kk -> arm = up * (1 - kk)), null));
    }

    private Seq reach(Seq q, float up) {
        return reach(q, up, 260, 300);
    }

    private void play(Seq q, Runnable done) {
        q.onDone = done;
        seqs.add(q);
    }

    void toast(String msg, float ms) {
        toast = msg;
        toastLeft = ms;
    }

    // ---------------- discoveries ----------------
    private void discover(String id) {
        if (!found.add(id)) return;
        if (found.size() == total) {
            toast("Ты нашёл всё на острове и в доме. Гномик доволен!", 7000);
            sfx("yay");
            for (int i = 0; i < 40; i++) {
                Keys kk = waapi(Keys.EASE_OUT).k(0, "tx", 0, "ty", 0, "op", 0).k(.2f, "op", 1)
                        .k(1, "tx", (rand() - .5f) * 200, "ty", -300 - rand() * 500, "op", 0).done();
                particle("dot", 200 + rand() * 1200, 900, kk, 3000 + rand() * 2000, rand() * 1500, null);
            }
        }
    }

    // ---------------- hotspots ----------------
    interface Act {
        void build(Seq q);
    }

    private static final class Spot {
        boolean in;
        String key, partRect;
        RectF rect;
        float walk;
        int face;
        Act act;
    }

    private final List<Spot> spots = new ArrayList<>();

    private Spot spot(boolean in, String key, RectF rect, float walk, int face, Act act) {
        Spot s = new Spot();
        s.in = in;
        s.key = key;
        s.rect = rect;
        s.walk = walk;
        s.face = face;
        s.act = act;
        spots.add(s);
        return s;
    }

    private static RectF R(float x, float y, float w, float h) {
        return new RectF(x, y, x + w, y + h);
    }

    private RectF partRect(String id, float pad) {
        Scene.Part p = part(id);
        if (p == null) return null;
        return new RectF(p.box.left - pad, p.box.top - pad, p.box.right + pad, p.box.bottom + pad);
    }

    private Keys keysOf(Object[]... frames) {
        Keys kk = waapi(Keys.EASE_OUT);
        for (Object[] f : frames) {
            float off = -1;
            Object[] kv = f;
            if (f.length % 2 == 1) {
                off = ((Number) f[0]).floatValue();
                kv = java.util.Arrays.copyOfRange(f, 1, f.length);
            }
            kk.k(off, kv);
        }
        return kk.done();
    }

    private static Object[] f(Object... kv) {
        return kv;
    }

    private void buildSpots() {
        // ---- island ----
        spot(false, "door", R(498, 484, 80, 86), 538, 0, this::enterHouse);
        spot(false, "beast", R(1095, 520, 190, 140), 1078, 1, q -> reach(q, -30).run(() -> {
            sfx("snort");
            poke("beast", keysOf(f("s", 1), f("sx", 1.05f, "sy", .93f, "ty", 3), f("sx", .97f, "sy", 1.06f), f("s", 1)), 900, .5f, 1);
            for (int i = 0; i < 6; i++) {
                Keys kk = waapi(Keys.EASE_OUT).k(0, "s", .6f, "op", 0).k(.2f, "op", 1).k(1, "tx", 20 + i * 8, "ty", -60 - i * 18, "s", 1.2f, "op", 0).done();
                particle("zz", 1250 + i * 6, 540, kk, 1800, 500 + i * 220, "z");
            }
            toast("Хррр… Зверь всхрапнул и снова уснул.", 4500);
        }));
        spot(false, "glowshrooms", R(810, 524, 32, 34), 806, 0, q -> reach(q, -30).run(() -> {
            sfx("sparkle");
            flash("glowshrooms", bright(2.6f), 1600);
        }));
        spot(false, "machine", R(975, 330, 160, 230), 985, 1, q -> reach(q, -60).run(() -> {
            sfx("whirr");
            speed(new String[]{"propeller", "gear-a", "gear-b", "gear-c", "gauge", "flag"}, 5, 3200);
        }).delay(600).run(() -> {
            sfx("musicbox");
            float ms = 4800;
            for (int i = 0; i < 9; i++) {
                Keys kk = waapi(Keys.EASE_OUT).k(0, "op", 0).k(.15f, "op", 1)
                        .k(1, "tx", -40 - rand() * 120, "ty", -80 - rand() * 120, "rot", (rand() - .5f) * 60, "op", 0).done();
                particle("note", 1000 + rand() * 20, 290, kk, 2200, i * (ms / 9), rand() < .5f ? "♪" : "♫");
            }
            toast("Граммофон на башне заиграл.", 4500);
        }));
        spot(false, "lantern", R(1146, 398, 40, 60), 1110, 1, q -> reach(q, -80).run(() -> {
            sfx("ding");
            poke("lantern", keysOf(f("rot", 0), f("rot", 16), f("rot", -12), f("rot", 7), f("rot", 0)), 2200, .5f, 0);
        }));
        spot(false, "chimney", R(598, 298, 84, 72), 612, 0, q -> reach(q, -75).run(() -> {
            sfx("whoosh");
            for (int i = 0; i < 9; i++) {
                float sc2 = 3 + rand() * 2;
                Keys kk = waapi(Keys.EASE_OUT).k(0, "s", .5f, "op", 0).k(.1f, "op", 1)
                        .k(1, "tx", 40 + rand() * 90, "ty", -120 - rand() * 120, "s", sc2, "op", 0).done();
                particle("puffx", 640, 320, kk, 2400, i * 90, null);
            }
        }));
        spot(false, "window", R(552, 432, 42, 40), 575, 0, q -> reach(q, -60).run(() -> {
            sfx("click");
            sc.extraFx.put("glow-window", new Scene.Fx(waapi(Keys.LINEAR).k(-1, "op", 1).k(-1, "op", .1f).k(-1, "op", 1).k(-1, "op", .2f).k(-1, "op", 1).done(), 900, 0, 0));
        }));
        spot(false, "moth", null, 880, 0, q -> q.run(() -> {
            sfx("buzz");
            flyOff("moth", new float[][]{{0, 0}, {-140, -90}, {-60, -200}, {120, -150}, {60, -40}, {0, 0}}, 3200, false);
        })).partRect = "moth";
        spot(false, "beetle", null, 700, 0, q -> q.run(() -> {
            sfx("buzz");
            flyOff("beetle", new float[][]{{0, 0}, {60, -40}, {120, 0}, {60, 40}, {0, 0}, {-60, -40}, {0, 0}}, 2600, true);
        })).partRect = "beetle";
        spot(false, "jelly", null, 470, 0, q -> q.run(() -> {
            sfx("sparkle");
            flash("jelly", bright(2.2f), 2000);
        })).partRect = "jelly";
        spot(false, "snail", null, 975, 0, q -> q.run(() -> {
            sfx("bloop");
            poke("snail-1", keysOf(f("s", 1), f("sx", .6f, "sy", .7f), f(.7f, "sx", .6f, "sy", .7f), f("s", 1)), 2200, .5f, .7f);
            toast("Улитка спряталась… и снова выглянула.", 4500);
        })).partRect = "snail-1";
        spot(false, "spider", R(1050, 450, 40, 40), 1060, 0, q -> reach(q, -50).run(() -> {
            sfx("bloop");
            poke("spider-1", keysOf(f("ty", 0), f("ty", 40), f(.6f, "ty", 34), f("ty", 0)), 2400, .5f, .5f);
        }));
        spot(false, "sky", R(-9999, -9999, 1, 1), 780, 0, q -> { });
        spot(false, "ladder", null, 905, 0, q -> q.run(() -> {
            sfx("creak");
            poke("ladder", keysOf(f("rot", 0), f("rot", 14), f("rot", -10), f("rot", 5), f("rot", 0)), 2400, .5f, 0);
        })).partRect = "ladder";
        // ---- inside the house ----
        spot(true, "exit", R(90, 580, 200, 330), 195, 0, this::leaveHouse);
        spot(true, "bed", R(410, 630, 360, 240), 600, 0, this::sleep);
        spot(true, "lamp", R(764, 405, 72, 95), 800, 0, q -> reach(q, -95).run(() -> {
            sfx("ding");
            poke("lamp", keysOf(f("rot", 0), f("rot", 10), f("rot", -8), f("rot", 4), f("rot", 0)), 2000, .5f, 0);
        }));
        spot(true, "stove", R(1215, 640, 180, 215), 1175, 1, q -> reach(q, -30).run(() -> {
            sfx("whoosh");
            sfx("crackle");
            flash("fire-back", bright(2), 1500);
            sc.extraFx.put("stoveglow", new Scene.Fx(waapi(Keys.LINEAR).k(-1, "s", 1).k(-1, "s", 1.5f).k(-1, "s", 1).done(), 1500, 0, 0));
            for (int i = 0; i < 18; i++) {
                Keys kk = waapi(Keys.EASE_OUT).k(0, "tx", 0, "ty", 0, "op", 1).k(1, "tx", (rand() - .5f) * 220, "ty", -60 - rand() * 160, "op", 0).done();
                particle("spark", 1300 + (rand() - .5f) * 60, 760, kk, 900 + rand() * 700, rand() * 300, null);
            }
        }));
        spot(true, "kettle", R(1255, 540, 120, 62), 1190, 1, q -> reach(q, -90).run(() -> {
            sfx("whistle");
            poke("kettle", keysOf(f("rot", 0), f("rot", -3), f("rot", 3), f("rot", -2), f("rot", 2), f("rot", 0)), 1600, .5f, 1);
            for (int i = 0; i < 14; i++) {
                Keys kk = waapi(Keys.EASE_OUT).k(0, "s", .5f, "op", 0).k(.1f, "op", 1)
                        .k(1, "tx", 30 + rand() * 80, "ty", -140 - rand() * 100, "s", 4, "op", 0).done();
                particle("puffx", 1362, 556, kk, 1800, i * 100, null);
            }
        }));
        spot(true, "clock", R(810, 336, 80, 225), 850, 0, q -> reach(q, -90).run(() -> {
            sfx("clock");
            speed(new String[]{"pendulum"}, 3, 2000);
        }));
        spot(true, "jar", R(445, 408, 48, 66), 470, 0, q -> reach(q, -95).run(() -> {
            sfx("sparkle");
            flash("jar", bright(2.4f), 1800);
            for (int i = 0; i < 12; i++) {
                Keys kk = waapi(Keys.EASE_OUT).k(0, "tx", 0, "ty", 0, "op", 1).k(1, "tx", (rand() - .5f) * 160, "ty", (rand() - .5f) * 140, "op", 0).done();
                particle("dot", 469, 445, kk, 1500, 0, null);
            }
        }));
        spot(true, "musicbox", R(846, 730, 72, 50), 860, 0, q -> reach(q, -20).run(() -> {
            sfx("musicbox");
            float ms = 4800;
            poke("crank", waapi(Keys.LINEAR).k(0, "rot", 0).k(1, "rot", -720).done(), ms, 0, 1);
            for (int i = 0; i < 12; i++) {
                Keys kk = waapi(Keys.EASE_OUT).k(0, "tx", 0, "ty", 0, "op", 0).k(.15f, "op", 1)
                        .k(1, "tx", (rand() - .5f) * 200, "ty", -140 - rand() * 120, "rot", (rand() - .5f) * 50, "op", 0).done();
                particle("note", 875, 720, kk, 2400, i * (ms / 12), rand() < .5f ? "♪" : "♫");
            }
        }));
        spot(true, "candle", R(926, 705, 34, 75), 930, 0, q -> reach(q, -15).run(() -> {
            sfx("click");
            flash("candle", waapi(Keys.LINEAR).k(-1, "br", 1, "s", 1).k(-1, "br", 1.8f, "s", 1.3f).k(-1, "br", 1, "s", 1).done(), 1200);
        }));
        spot(true, "window-in", R(1034, 286, 150, 160), 1100, 0, q -> q.run(() -> {
            look = -12;
            lookTo = -12;
            sfx("sparkle");
            Keys kk = waapi(Keys.EASE_OUT).k(0, "rot", 20, "op", 0).k(.2f, "op", 1).k(1, "tx", 90, "ty", 40, "rot", 20, "op", 0).done();
            particle("streak", 1060, 320, kk, 900, 0, null);
        }).delay(1600).run(() -> lookTo = 0));
        spot(true, "hook", R(296, 570, 110, 190), 330, 0, q -> reach(q, -70).run(() -> {
            sfx("click");
            toast("Запасная шапка и любимый шарф.", 2500);
        }));
        spot(true, "pet", R(1122, 846, 108, 60), 1100, 1, q -> reach(q, 10, 300, 500).run(() -> {
            sfx("purr");
            poke("pet", keysOf(f("s", 1), f("sx", 1.06f, "sy", .92f), f("sx", .98f, "sy", 1.05f), f("s", 1)), 1100, .5f, 1);
            for (int i = 0; i < 4; i++) {
                Keys kk = waapi(Keys.EASE_OUT).k(0, "s", .6f, "op", 0).k(.2f, "op", 1).k(1, "tx", (i - 1.5f) * 18, "ty", -70, "s", 1, "op", 0).done();
                particle("note", 1180, 840, kk, 1400, i * 200, "♥");
            }
            toast("Моховой зверёк мурчит у тёплой печки.", 3000);
        }));
        spot(true, "front-shrooms", R(0, 880, 130, 120), 180, 0, q -> q.run(() -> {
            boing(1.4f);
            poke("front-left", keysOf(f("s", 1), f("sx", 1.1f, "sy", .85f), f("sx", .95f, "sy", 1.08f), f("s", 1)), 700, .5f, 1);
        }));
        // ---- every mushroom cap on the island bounces ----
        for (Scene.Part p : sc.parts.values()) {
            if (!p.id.startsWith("shroom-")) continue;
            float cx = p.box.centerX();
            final Scene.Part pp = p;
            Spot s = spot(false, "mushrooms", new RectF(p.box.left - 4, p.box.top - 4, p.box.right + 4, p.box.bottom + 4), cx < 760 ? cx + 22 : cx - 22, 0,
                    q -> reach(q, -40, 180, 120).run(() -> {
                        boing(Math.min(2.2f, pp.box.height() / 60));
                        poke(pp.id, keysOf(f("s", 1), f("sx", 1.18f, "sy", .78f), f("sx", .9f, "sy", 1.15f), f("sx", 1.04f, "sy", .97f), f("s", 1)), 700, .5f, 1);
                        for (int i = 0; i < 10; i++) {
                            Keys kk = waapi(Keys.EASE_OUT).k(0, "tx", 0, "ty", 0, "s", 1, "op", 1)
                                    .k(1, "tx", (rand() - .5f) * 70, "ty", -30 - rand() * 60, "s", .4f, "op", 0).done();
                            particle("dot", cx + (rand() - .5f) * pp.box.width() * .6f, pp.box.top + 6, kk, 1400 + rand() * 600, 0, null);
                        }
                    }));
        }
    }

    private RectF rectOf(Spot s) {
        return s.partRect != null ? partRect(s.partRect, s.partRect.equals("jelly") ? 8 : 10) : s.rect;
    }

    private Spot hit(float px, float py) {
        Spot best = null;
        float area = 1e9f;
        for (Spot s : spots) {
            if (s.in != inside) continue;
            RectF rr = rectOf(s);
            if (rr == null) continue;
            if (rr.contains(px, py) && rr.width() * rr.height() < area) {
                best = s;
                area = rr.width() * rr.height();
            }
        }
        return best;
    }

    // ---------------- the island and the house ----------------
    private void doorFrame(int f) {
        for (int i = 0; i < 3; i++) {
            Scene.Part d = part("door-" + i);
            if (d != null) d.vis = i == f ? 1 : 0;
        }
        Scene.Part dw = part("doorway");
        if (dw != null) dw.vis = f > 0 ? 1 : 0;
    }

    private Seq doorOut(Seq q, boolean open) {
        int[] seq = open ? new int[]{1, 2} : new int[]{1, 0};
        for (int f : seq) q.delay(180).run(() -> doorFrame(f));
        return q;
    }

    private Seq swapScene(Seq q, boolean toIn, float nx, float ndir) {
        return q.run(() -> curtainTo = 1).delay(380).run(() -> {
            inside = toIn;
            x = nx;
            dir = ndir;
            target = Float.NaN;
            sleeping = false;
            snd.setInside(toIn);
            curtainTo = 0;
        }).delay(380);
    }

    private void enterHouse(Seq q) {
        reach(q, -40, 200, 100).run(() -> sfx("creak"));
        doorOut(q, true).tween(450, kk -> fade = 1 - kk);
        swapScene(q, true, 200, 1).run(() -> {
            fade = 1;
            doorFrame(0);
            if (!found.contains("door")) toast("Внутри тепло. Тапни по двери, чтобы выйти обратно.", 4500);
        });
    }

    private void leaveHouse(Seq q) {
        q.run(() -> {
            sfx("creak");
            doorFrame(2);
        });
        swapScene(q, false, 538, 1).run(() -> fade = 0).tween(400, kk -> fade = kk).run(() -> target = 590).until(() -> Float.isNaN(target));
        doorOut(q, false).run(() -> sfx("click"));
    }

    private void sleep(Seq q) {
        q.run(() -> {
            sleeping = true;
            blink = .08f;
            sfx("snore");
            toast("Тсс… гномик спит.", 3000);
        });
        for (int i = 0; i < 4; i++)
            q.delay(1300).run(() -> {
                sfx("snore");
                Keys kk = waapi(Keys.EASE_OUT).k(0, "s", .6f, "op", 0).k(.2f, "op", 1).k(1, "tx", 40, "ty", -140, "s", 1.4f, "op", 0).done();
                particle("zz", 540, 700, kk, 2200, 0, "z");
            });
        q.run(() -> {
            sleeping = false;
            blink = 1;
            x = 600;
        });
    }

    // ---------------- input ----------------
    private void goTo(float tx, Spot s) {
        action = s;
        target = Math.max(minX(), Math.min(maxX(), tx));
    }

    /** A tap at screen px. */
    void tap(float sx, float sy) {
        if (!started) {
            if (loaded && (playBtn.contains(sx, sy) || startA >= 1)) start();
            return;
        }
        if (sndBtn.contains(sx, sy)) {
            snd.setMuted(!snd.muted());
            return;
        }
        if (busy || sleeping) return;
        float px = (sx - ox) / k, py = (sy - oy) / k;
        Spot s = hit(px, py);
        if (s != null) {
            goTo(s.walk, s);
            return;
        }
        if (!inside) {
            float gy = groundY(Math.max(380, Math.min(1230, px)));
            if (px > 360 && px < 1250 && py > gy - 140 && py < 990) goTo(px, null);
            else {
                sfx("sparkle");
                Keys kk = waapi(Keys.EASE_OUT).k(0, "rot", 18, "sx", .2f, "op", 0).k(.2f, "op", 1).k(1, "tx", 160, "ty", 52, "rot", 18, "sx", 1, "op", 0).done();
                particle("streak", px - 60, py, kk, 900, 0, null);
                discover("sky");
            }
        } else goTo(px, null);
    }

    private void start() {
        started = true;
        snd.start();
        toast("Тапни по земле — гномик пойдёт. Тапни по чему-нибудь — он с этим поиграет. Загляни и в дом.", 7000);
    }

    // ---------------- main loop ----------------
    private void arrive() {
        Spot s = action;
        action = null;
        if (s == null) return;
        if (s.face != 0) dir = s.face;
        else {
            RectF rr = rectOf(s);
            if (rr != null) dir = rr.centerX() >= x ? 1 : -1;
        }
        busy = true;
        Seq q = new Seq();
        s.act.build(q);
        play(q, () -> {
            discover(s.key);
            busy = false;
        });
    }

    /** One 40 ms step of everything. */
    void tick() {
        float dt = FRAME / 1000f;
        t += dt;
        boolean moving = false;
        if (!Float.isNaN(target) && !sleeping) {
            float dx = target - x;
            if (Math.abs(dx) < 1.5f) {
                x = target;
                target = Float.NaN;
                arrive();
            } else {
                dir = Math.signum(dx);
                float step = Math.min(Math.abs(dx), speed() * dt);
                x += dir * step;
                phase += step / stride();
                moving = true;
                int st = (int) Math.signum(Math.sin(phase));
                if (st != lastStep) {
                    lastStep = st;
                    if (inside) snd.play("step_in", 1, 1 + rand() * .2f);
                    else snd.play("step_out", 1, .9f + rand() * .2f);
                }
            }
        }
        walk += ((moving ? 1 : 0) - walk) * Math.min(1, dt * 10);
        if (!moving && walk < .02f) phase = 0;
        beam += ((moving || busy ? 0 : .95f) - beam) * Math.min(1, dt * 3);
        if (!sleeping) {
            if (t > nextBlink) {
                blink = .1f;
                if (t > nextBlink + .12f) {
                    blink = 1;
                    nextBlink = t + 2.5f + rand() * 3;
                }
            }
            if (!moving && !busy && t > nextLook) {
                lookTo = new float[]{-8, 6, -4, 0}[rnd.nextInt(4)];
                nextLook = t + 3 + rand() * 4;
            }
            if (moving) lookTo = 0;
            look += (lookTo - look) * Math.min(1, dt * 3);
        }
        for (int i = 0; i < seqs.size(); i++) {
            Seq q = seqs.get(i);
            if (q.tick(FRAME)) {
                seqs.remove(i--);
                if (q.onDone != null) q.onDone.run();
            }
        }
        for (Iterator<Particle> it = fx.iterator(); it.hasNext(); ) {
            Particle p = it.next();
            if ((p.t += FRAME) >= p.delay + p.dur) it.remove();
        }
        sc.tick(FRAME);
        snd.tick(FRAME);
        // interface fades
        float fs = FRAME / 350f;
        curtain += Math.max(-fs, Math.min(fs, curtainTo - curtain));
        if (started) startA = Math.max(0, startA - FRAME / 800f);
        if (started) foundA = Math.min(1, foundA + FRAME / 600f);
        toastLeft -= FRAME;
        toastA = toastLeft > 0 ? Math.min(1, toastA + FRAME / 600f) : Math.max(0, toastA - FRAME / 600f);
    }

    // ---------------- drawing ----------------
    void draw(Canvas c, int w, int h) {
        vw = w;
        vh = h;
        k = Math.min(w / Scene.W, h / Scene.H);
        ox = (w - Scene.W * k) / 2;
        oy = (h - Scene.H * k) / 2;
        u = Math.min(h / 400f, w / 700f);
        c.drawColor(0xff061210);
        c.save();
        c.translate(ox, oy);
        c.scale(k, k);
        c.clipRect(0, 0, Scene.W, Scene.H);
        sc.draw(c, inside, cc -> {
            drawHero(cc);
            drawFx(cc);
        });
        if (curtain > 0) {
            ui.setShader(null);
            ui.setColor(0xff000000);
            ui.setAlpha(Math.round(curtain * 255));
            c.drawRect(0, 0, Scene.W, Scene.H, ui);
        }
        c.restore();
        drawUi(c);
    }

    private void limb(Canvas c, int i, float alpha) {
        if (alpha <= .004f) return;
        bmp.setAlpha(Math.round(Math.min(1, alpha) * 255));
        c.drawBitmap(limb[i], null, limbBox[i], bmp);
    }

    private void drawHero(Canvas c) {
        float scl = scale(), w = walk, sn = (float) Math.sin(phase), cs = Math.abs((float) Math.cos(phase));
        int save = fade < 1 ? c.saveLayerAlpha(0, 0, Scene.W, Scene.H, Math.round(Math.max(0, fade) * 255)) : c.save();
        if (fade <= 0) {
            c.restoreToCount(save);
            return;
        }
        if (sleeping) {
            c.translate(560, 752);
            c.scale(scl, scl);
            c.rotate(-90);
            c.translate(-781, -512);
        } else {
            c.translate(x, feet(x));
            c.scale(scl * dir, scl);
            c.translate(-781, -548);
        }
        float breathe = (1 - w) * (float) Math.sin(t * 1.8) * .45f;
        // shadow
        c.save();
        c.translate(781, 549);
        c.scale(1 - .12f * cs * w, 1);
        c.translate(-781, -549);
        limb(c, SHADOW, 1);
        c.restore();
        c.save();
        c.rotate(sn * 30 * w, 775, 532);
        limb(c, LEGL, 1);
        c.restore();
        c.save();
        c.rotate(-sn * 30 * w, 786, 532);
        limb(c, LEGR, 1);
        c.restore();
        c.save();
        c.translate(0, -cs * 2.4f * w + breathe);
        c.save();
        c.rotate(-sn * 22 * w + armL, 770, 517);
        limb(c, ARML, 1);
        c.restore();
        limb(c, BODY, 1);
        c.save();
        c.rotate(sn * 9 * w + arm, 791, 517);
        limb(c, BEAM, !inside && !sleeping ? beam : 0);
        limb(c, ARMR, 1);
        c.restore();
        c.save();
        c.rotate(look + sn * 2.5f * w, 781, 512);
        limb(c, HEAD, 1);
        c.translate(0, 496 * (1 - blink));
        c.scale(1, blink);
        limb(c, EYES, 1);
        c.restore();
        c.restore();
        c.restoreToCount(save);
    }

    private void drawFx(Canvas c) {
        for (Particle p : fx) {
            if (p.in != inside) continue;
            float x01 = Math.max(0, Math.min(1, (p.t - p.delay) / p.dur));
            p.k.sample(x01, s);
            float a = s[Keys.OP];
            if (a <= .004f) continue;
            c.save();
            float cx, cy;
            switch (p.kind) {
                case "dot": cx = p.x + 3; cy = p.y + 3; break;
                case "spark": cx = p.x + 2; cy = p.y + 2; break;
                case "puffx": cx = p.x + 12; cy = p.y + 12; break;
                case "streak": cx = p.x + 60; cy = p.y + 1; break;
                default: cx = p.x + 8; cy = p.y + 12;
            }
            m.reset();
            Keys.transform(m, s, cx, cy);
            c.concat(m);
            switch (p.kind) {
                case "dot": dot(c, dotP, cx, cy, 14, a); break;
                case "spark": dot(c, sparkP, cx, cy, 10, a); break;
                case "puffx": dot(c, puffP, cx, cy, 17, a); break;
                case "streak":
                    c.translate(p.x, p.y);
                    streakP.setAlpha(Math.round(a * 255));
                    c.drawRoundRect(0, 0, 120, 2, 1, 1, streakP);
                    break;
                default: {
                    boolean zz = p.kind.equals("zz");
                    text.setTypeface(zz ? Typeface.create(Typeface.SERIF, Typeface.BOLD) : Typeface.SERIF);
                    text.setTextSize(zz ? 20 : 22);
                    text.setColor(zz ? 0xffe6eedf : 0xfff3d27a);
                    text.setShadowLayer(6, 0, 0, zz ? 0x99c8e6dc : 0xb3f3d27a);
                    text.setAlpha(Math.round(a * 255));
                    c.drawText(p.text, p.x, p.y + 20, text);
                    text.clearShadowLayer();
                    text.setTypeface(font);
                }
            }
            c.restore();
        }
    }

    private static void dot(Canvas c, Paint p, float cx, float cy, float r, float a) {
        p.setAlpha(Math.round(Math.min(1, a) * 255));
        c.save();
        c.translate(cx, cy);
        c.scale(r, r);
        c.drawCircle(0, 0, 1, p);
        c.restore();
    }

    // ---------------- interface ----------------
    private void pill(Canvas c, RectF rr, int color) {
        ui.setShader(null);
        ui.setStyle(Paint.Style.FILL);
        ui.setColor(color);
        c.drawRoundRect(rr, rr.height() / 2, rr.height() / 2, ui);
    }

    private StaticLayout layout(String s, TextPaint p, int width) {
        if (Build.VERSION.SDK_INT >= 23)
            return StaticLayout.Builder.obtain(s, 0, s.length(), p, width).setAlignment(Layout.Alignment.ALIGN_CENTER).setLineSpacing(0, 1.15f).build();
        return new StaticLayout(s, p, width, Layout.Alignment.ALIGN_CENTER, 1.15f, 0, false);
    }

    private void drawUi(Canvas c) {
        text.setTypeface(font);
        text.clearShadowLayer();
        // discoveries counter
        if (foundA > 0) {
            text.setTextSize(17 * u);
            String a = "найдено ", n = String.valueOf(found.size()), b = " из " + total;
            float tw = text.measureText(a) + text.measureText(n) + text.measureText(b);
            r.set(16 * u, 12 * u, 16 * u + tw + 24 * u, 12 * u + 32 * u);
            pill(c, r, ((int) (foundA * 0xb8) << 24) | 0x081412);
            float tx = r.left + 12 * u, ty = r.centerY() + 6 * u;
            text.setColor(0xffefe6c8);
            text.setAlpha(Math.round(foundA * 255));
            c.drawText(a, tx, ty, text);
            tx += text.measureText(a);
            text.setColor(0xfff3d27a);
            text.setAlpha(Math.round(foundA * 255));
            c.drawText(n, tx, ty, text);
            tx += text.measureText(n);
            text.setColor(0xffefe6c8);
            text.setAlpha(Math.round(foundA * 255));
            c.drawText(b, tx, ty, text);
        }
        // sound toggle
        if (started) {
            float d = 46 * u, cx = vw - 16 * u - d / 2, cy = 10 * u + d / 2;
            sndBtn.set(cx - d / 2 - 10 * u, cy - d / 2 - 10 * u, cx + d / 2 + 10 * u, cy + d / 2 + 10 * u);
            ui.setShader(null);
            ui.setStyle(Paint.Style.FILL);
            ui.setColor(0x8c0a1816);
            c.drawCircle(cx, cy, d / 2, ui);
            ui.setStyle(Paint.Style.STROKE);
            ui.setStrokeWidth(u);
            ui.setColor(0x59f0e6c8);
            c.drawCircle(cx, cy, d / 2, ui);
            c.save();
            c.translate(cx - 11 * u, cy - 11 * u);
            c.scale(22 * u / 24, 22 * u / 24);
            Path sp = new Path();
            sp.moveTo(4, 9);
            sp.lineTo(8, 9);
            sp.lineTo(13, 5);
            sp.lineTo(13, 19);
            sp.lineTo(8, 15);
            sp.lineTo(4, 15);
            sp.close();
            ui.setStyle(Paint.Style.FILL);
            ui.setColor(0xffefe6c8);
            c.drawPath(sp, ui);
            ui.setStyle(Paint.Style.STROKE);
            ui.setStrokeWidth(1.6f);
            ui.setStrokeCap(Paint.Cap.ROUND);
            if (snd.muted()) {
                c.drawLine(16.5f, 9.5f, 21.5f, 14.5f, ui);
                c.drawLine(21.5f, 9.5f, 16.5f, 14.5f, ui);
            } else {
                c.drawArc(new RectF(12.2f, 8.5f, 19.4f, 15.5f), -60, 120, false, ui);
                c.drawArc(new RectF(12.5f, 6f, 24.5f, 18f), -60, 120, false, ui);
            }
            c.restore();
            ui.setStyle(Paint.Style.FILL);
        }
        // toast
        if (toastA > 0 && !toast.isEmpty()) {
            text.setTextSize(18 * u);
            text.setColor(0xffefe6c8);
            int maxW = (int) Math.min(560 * u, vw * .86f) - (int) (32 * u);
            StaticLayout l = layout(toast, text, maxW);
            float lw = 0;
            for (int i = 0; i < l.getLineCount(); i++) lw = Math.max(lw, l.getLineWidth(i));
            float bw = lw + 32 * u, bh = l.getHeight() + 16 * u;
            r.set(vw / 2 - bw / 2, vh - 22 * u - bh, vw / 2 + bw / 2, vh - 22 * u);
            ui.setShader(null);
            ui.setColor(((int) (toastA * 0xb8) << 24) | 0x081412);
            c.drawRoundRect(r, 14 * u, 14 * u, ui);
            text.setAlpha(Math.round(toastA * 255));
            c.save();
            c.translate(vw / 2 - maxW / 2f, r.top + 8 * u);
            l.draw(c);
            c.restore();
        }
        // start screen
        if (startA > 0) {
            ui.setShader(new RadialGradient(vw / 2, vh * .4f, Math.max(vw, vh) * .75f, 0x590a1e1c, 0xeb030a09, Shader.TileMode.CLAMP));
            ui.setAlpha(Math.round(startA * 255));
            c.drawRect(0, 0, vw, vh, ui);
            ui.setShader(null);
            int al = Math.round(startA * 255);
            text.setTextSize(Math.min(84 * u, vw * .09f) * 1.15f);
            text.setTextAlign(Paint.Align.CENTER);
            text.setColor(0xfff4ecd2);
            text.setShadowLayer(18 * u, 0, 2 * u, 0x40f3d27a);
            text.setAlpha(al);
            float titleY = vh * .36f;
            c.drawText("Остров-пень", vw / 2, titleY, text);
            text.clearShadowLayer();
            text.setTextAlign(Paint.Align.LEFT);
            text.setTextSize(20 * u);
            text.setColor(0xb3efe6c8);
            text.setAlpha(Math.round(startA * 0xb3));
            int pw = (int) Math.min(34 * 20 * u, vw * .8f);
            StaticLayout l = layout("Маленький гномик живёт на летающем пне. Тапни по земле, чтобы он пошёл туда, а по чему-нибудь интересному, чтобы он с этим поиграл. Загляни и в дом.", text, pw);
            c.save();
            c.translate(vw / 2 - pw / 2f, titleY + 26 * u);
            l.draw(c);
            c.restore();
            text.setTextSize(24 * u);
            String label = loaded ? "Играть" : "Загрузка…";
            float bw = text.measureText(label) + 68 * u, bh = 50 * u, by = titleY + 26 * u + l.getHeight() + 22 * u;
            playBtn.set(vw / 2 - bw / 2, by, vw / 2 + bw / 2, by + bh);
            ui.setColor(0x1ff3d27a);
            ui.setAlpha(Math.round(startA * 0x1f));
            c.drawRoundRect(playBtn, bh / 2, bh / 2, ui);
            ui.setStyle(Paint.Style.STROKE);
            ui.setStrokeWidth(Math.max(1, u));
            ui.setColor(0x8cf3d27a);
            ui.setAlpha(Math.round(startA * 0x8c));
            c.drawRoundRect(playBtn, bh / 2, bh / 2, ui);
            ui.setStyle(Paint.Style.FILL);
            text.setColor(0xfff4ecd2);
            text.setAlpha(al);
            text.setTextAlign(Paint.Align.CENTER);
            c.drawText(label, vw / 2, playBtn.centerY() + 8 * u, text);
            text.setTextAlign(Paint.Align.LEFT);
        }
    }
}
