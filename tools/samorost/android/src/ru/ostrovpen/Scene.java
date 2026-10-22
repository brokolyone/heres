package ru.ostrovpen;

import android.content.res.AssetManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.BitmapShader;
import android.graphics.Canvas;
import android.graphics.ColorMatrix;
import android.graphics.ColorMatrixColorFilter;
import android.graphics.LinearGradient;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffXfermode;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * Both scenes of the game, island and house interior, as ordered draw lists (see export_assets.py):
 * full-stage backdrops, animated sprites with keyframe loops, and the small procedural extras
 * (stars, smoke, spores, glows, steam, the stove flames, the room shadow and the film grain).
 */
final class Scene {
    static final float W = 1600, H = 1000;

    /** One animated sprite. Coordinates are stage px; origin is absolute. */
    static final class Part {
        String id;
        Bitmap bmp;
        final RectF box = new RectF();
        float ox, oy, dur, delay;
        Keys keys;
        final List<Part> below = new ArrayList<>(), above = new ArrayList<>();
        float clock, rate = 1, rateLeft;
        float vis = 1;
        Fx poke, fly, flash;
    }

    /** A one-shot keyframe effect: Web Animations semantics (whole-run easing), with its own origin. */
    static final class Fx {
        Keys k;
        float dur, t, ox, oy;

        Fx(Keys k, float dur, float ox, float oy) {
            this.k = k;
            this.dur = dur;
            this.ox = ox;
            this.oy = oy;
        }

        boolean done() {
            return t >= dur;
        }

        float x() {
            return Math.max(0, Math.min(1, t / dur));
        }
    }

    interface Layer {
        void draw(Canvas c);
    }

    final List<Object> out = new ArrayList<>(), in = new ArrayList<>();
    final Map<String, Part> parts = new HashMap<>();
    final Map<String, float[]> extraBoxes = new HashMap<>();
    final Map<String, Fx> extraFx = new HashMap<>();
    private final Map<String, JSONObject> anims = new HashMap<>();
    private final Map<String, Bitmap> backdrops = new HashMap<>();
    float ms;

    private final Paint bmpPaint = new Paint(Paint.FILTER_BITMAP_FLAG | Paint.ANTI_ALIAS_FLAG);
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Matrix m = new Matrix();
    private final float[] s = new float[Keys.N], s2 = new float[Keys.N];
    private final Map<Integer, ColorMatrixColorFilter> bright = new HashMap<>();

    Scene(AssetManager am) throws Exception {
        JSONObject j = new JSONObject(read(am, "scene.json"));
        JSONObject an = j.getJSONObject("anims");
        for (java.util.Iterator<String> it = an.keys(); it.hasNext(); ) {
            String k = it.next();
            anims.put(k, an.getJSONObject(k));
        }
        load(am, j.getJSONArray("out"), out);
        load(am, j.getJSONArray("in"), in);
        initExtras(am);
    }

    static String read(AssetManager am, String name) throws IOException {
        try (InputStream is = am.open(name)) {
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] b = new byte[65536];
            int n;
            while ((n = is.read(b)) > 0) bo.write(b, 0, n);
            return bo.toString("UTF-8");
        }
    }

    static Bitmap bitmap(AssetManager am, String name) throws IOException {
        BitmapFactory.Options o = new BitmapFactory.Options();
        o.inPreferredConfig = Bitmap.Config.ARGB_8888;
        try (InputStream is = am.open(name)) {
            Bitmap b = BitmapFactory.decodeStream(is, null, o);
            if (b == null) throw new IOException("cannot decode " + name);
            return b;
        }
    }

    private void load(AssetManager am, JSONArray items, List<Object> into) throws Exception {
        for (int i = 0; i < items.length(); i++) {
            JSONObject it = items.getJSONObject(i);
            String t = it.getString("t");
            if (t.equals("img")) {
                String f = it.getString("f");
                Bitmap b = bitmap(am, "img/" + f);
                backdrops.put(f, b);
                into.add(b);
            } else if (t.equals("part")) {
                into.add(part(am, it));
            } else if (t.equals("hero")) {
                into.add("hero");
            } else {
                String kind = it.getString("kind");
                if (kind.equals("glow")) {
                    String id = it.getString("id");
                    extraBoxes.put(id, new float[]{(float) it.getDouble("x"), (float) it.getDouble("y"),
                            (float) it.getDouble("w"), (float) it.getDouble("h"), (float) it.getDouble("delay")});
                    into.add("glow:" + id);
                } else into.add(kind);
            }
        }
    }

    private Part part(AssetManager am, JSONObject it) throws Exception {
        Part p = new Part();
        p.id = it.getString("id");
        p.bmp = bitmap(am, "img/" + it.getString("f"));
        JSONArray b = it.getJSONArray("box");
        p.box.set((float) b.getDouble(0), (float) b.getDouble(1), (float) (b.getDouble(0) + b.getDouble(2)), (float) (b.getDouble(1) + b.getDouble(3)));
        JSONArray o = it.getJSONArray("o");
        p.ox = (float) o.getDouble(0);
        p.oy = (float) o.getDouble(1);
        p.dur = (float) it.getDouble("dur");
        p.delay = (float) it.getDouble("delay");
        p.keys = keys(it.getString("anim"), it.getJSONObject("vars"));
        JSONArray bl = it.getJSONArray("below"), ab = it.getJSONArray("above");
        for (int i = 0; i < bl.length(); i++) p.below.add(part(am, bl.getJSONObject(i)));
        for (int i = 0; i < ab.length(); i++) p.above.add(part(am, ab.getJSONObject(i)));
        parts.put(p.id, p);
        return p;
    }

    /** The named CSS animation as tracks, with its variables resolved for one part. */
    Keys keys(String name, JSONObject vars) throws Exception {
        JSONObject a = anims.get(name);
        Keys k = new Keys(Keys.easeOf(a.getString("ease")), true);
        JSONObject dv = a.getJSONObject("vars"), tr = a.getJSONObject("tracks");
        for (java.util.Iterator<String> it = tr.keys(); it.hasNext(); ) {
            String prop = it.next();
            JSONArray pts = tr.getJSONArray(prop);
            int p = Keys.prop(prop);
            k.t[p] = new float[pts.length()];
            k.v[p] = new float[pts.length()];
            for (int i = 0; i < pts.length(); i++) {
                JSONArray pt = pts.getJSONArray(i);
                k.t[p][i] = (float) pt.getDouble(0);
                Object v = pt.get(1);
                if (v instanceof Number) k.v[p][i] = ((Number) v).floatValue();
                else {
                    String e = (String) v;
                    boolean neg = e.startsWith("-");
                    String var = neg ? e.substring(1) : e;
                    double x = vars.has(var) ? vars.getDouble(var) : dv.getDouble(var);
                    k.v[p][i] = (float) (neg ? -x : x);
                }
            }
        }
        return k;
    }

    // ---------------- time ----------------
    void tick(float dt) {
        ms += dt;
        for (Part p : parts.values()) {
            p.clock += dt * p.rate;
            if (p.rateLeft > 0 && (p.rateLeft -= dt) <= 0) p.rate = 1;
            if (p.poke != null && (p.poke.t += dt) >= p.poke.dur) p.poke = null;
            if (p.fly != null && (p.fly.t += dt) >= p.fly.dur) p.fly = null;
            if (p.flash != null && (p.flash.t += dt) >= p.flash.dur) p.flash = null;
        }
        for (java.util.Iterator<Fx> it = extraFx.values().iterator(); it.hasNext(); ) {
            Fx f = it.next();
            if ((f.t += dt) >= f.dur) it.remove();
        }
    }

    private static float loop(float clock, float delay, float dur) {
        float x = (clock - delay) % dur;
        if (x < 0) x += dur;
        return x / dur;
    }

    // ---------------- drawing ----------------
    void draw(Canvas c, boolean inside, Layer hero) {
        for (Object it : inside ? in : out) {
            if (it instanceof Bitmap) {
                bmpPaint.setAlpha(255);
                bmpPaint.setColorFilter(null);
                c.drawBitmap((Bitmap) it, null, stageRect, bmpPaint);
            } else if (it instanceof Part) drawPart(c, (Part) it, 1, 1);
            else if (it.equals("hero")) hero.draw(c);
            else drawExtra(c, (String) it);
        }
    }

    private ColorMatrixColorFilter brightness(float b) {
        int q = Math.round(b * 50);
        if (q == 50) return null;
        ColorMatrixColorFilter f = bright.get(q);
        if (f == null) {
            float x = q / 50f;
            ColorMatrix cm = new ColorMatrix(new float[]{x, 0, 0, 0, 0, 0, x, 0, 0, 0, 0, 0, x, 0, 0, 0, 0, 0, 1, 0});
            bright.put(q, f = new ColorMatrixColorFilter(cm));
        }
        return f;
    }

    private void drawPart(Canvas c, Part p, float alpha, float br) {
        p.keys.sample(loop(p.clock, p.delay, p.dur), s);
        float a = alpha * s[Keys.OP] * p.vis, b = br * s[Keys.BR];
        int save = c.save();
        m.reset();
        if (p.fly != null) {
            p.fly.k.sample(p.fly.x(), s2);
            Keys.transform(m, s2, p.fly.ox, p.fly.oy);
        }
        if (p.flash != null) {
            p.flash.k.sample(p.flash.x(), s2);
            a *= s2[Keys.OP];
            b *= s2[Keys.BR];
            if (p.flash.k.hasTransform()) {
                Keys.transform(m, s2, p.flash.ox, p.flash.oy);
            }
        }
        Keys.transform(m, s, p.ox, p.oy);
        c.concat(m);
        if (a > 0.004f) {
            for (Part ch : p.below) drawPart(c, ch, a, b);
            if (p.poke != null) {
                c.save();
                m.reset();
                p.poke.k.sample(p.poke.x(), s2);
                Keys.transform(m, s2, p.poke.ox, p.poke.oy);
                c.concat(m);
            }
            bmpPaint.setAlpha(Math.round(Math.min(1, a) * 255));
            bmpPaint.setColorFilter(brightness(b));
            c.drawBitmap(p.bmp, null, p.box, bmpPaint);
            bmpPaint.setColorFilter(null);
            if (p.poke != null) c.restore();
            for (Part ch : p.above) drawPart(c, ch, a, b);
        }
        c.restoreToCount(save);
    }

    // ---------------- procedural extras ----------------
    private static final class Dot {
        float x, y, dur, delay, dx, dy, off, r;
        int kind;
    }

    private final List<Dot> stars = new ArrayList<>(), spores = new ArrayList<>(), dust = new ArrayList<>();
    private Paint[] starPaint, sporePaint;
    private final float[] starR = {1.4f, 1.8f, 2.2f, 2.8f};
    private Keys twinkle, sporeK, moonK, shootK, puffK, fallK, flickerK, flameK, emberK;
    private final Keys[] steamK = new Keys[6];
    private final float[] puffSx = new float[6];
    private Paint moonPaint, shootPaint, puffPaint, emberPaint, steamPaint, leafPaint, leafVein, glowWin, glowStove;
    private final Paint screen = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path leaf = new Path(), ovalPath = new Path();
    private final RectF stageRect = new RectF(0, 0, W, H);

    private Path oval(float l, float t, float r, float b) {
        ovalPath.reset();
        ovalPath.addOval(l, t, r, b, Path.Direction.CW);
        return ovalPath;
    }
    private Bitmap shade, vignette;
    private Paint grainPaint;
    private static final float[][] FLAMES = {{0, 24, 40, 900, -100}, {14, 26, 56, 700, -400}, {32, 24, 48, 1100, -200}, {48, 26, 58, 800, -600}, {62, 22, 38, 1000, -300}};
    private static final float[][] EMBERS = {{20, -200}, {36, -1100}, {54, -700}, {70, -1600}, {44, -2200}};
    private final Paint[] flamePaint = new Paint[FLAMES.length];

    private static void sporeSize(Dot d) {
        d.off = new float[]{1.5f, 1, 2.5f}[d.kind];
        d.r = new float[]{9.5f, 8, 2.5f}[d.kind];
    }

    private static int argb(float a, int r, int g, int b) {
        return (Math.round(Math.max(0, Math.min(1, a)) * 255) << 24) | (r << 16) | (g << 8) | b;
    }

    /** A dot with a CSS-like soft box-shadow: core radius, glow out to spread+blur. */
    private static Paint dotPaint(float core, int coreRgb, float spread, float blur, float ga, int glowRgb) {
        float outer = spread + blur;
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        int gr = (glowRgb >> 16) & 255, gg = (glowRgb >> 8) & 255, gb = glowRgb & 255;
        int cr = (coreRgb >> 16) & 255, cg = (coreRgb >> 8) & 255, cb = coreRgb & 255;
        p.setShader(new RadialGradient(0, 0, 1,
                new int[]{argb(1, cr, cg, cb), argb(1, cr, cg, cb), argb(ga, gr, gg, gb), argb(ga * .5f, gr, gg, gb), argb(0, gr, gg, gb)},
                new float[]{0, core / outer, Math.min(.99f, (core + .6f) / outer), Math.min(.995f, spread / outer + (1 - spread / outer) * .35f), 1},
                Shader.TileMode.CLAMP));
        return p;
    }

    private static Paint radial(int[] colors, float[] stops) {
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setShader(new RadialGradient(0, 0, 1, colors, stops, Shader.TileMode.CLAMP));
        return p;
    }

    private void initExtras(AssetManager am) throws Exception {
        Random r = new Random(7);
        for (int i = 0; i < 46; i++) {
            Dot d = new Dot();
            do {
                d.x = 20 + r.nextFloat() * 1560;
                d.y = 15 + r.nextFloat() * 605;
            } while (!((d.x - 1260) * (d.x - 1260) + (d.y - 230) * (d.y - 230) > 200 * 200 && !(d.x > 330 && d.x < 1270 && d.y > 330)));
            d.kind = r.nextInt(4);
            d.off = starR[d.kind] / 2;
            d.r = starR[d.kind] / 2 + 5;
            d.dur = new float[]{2000, 3000, 4000, 6000}[r.nextInt(4)];
            d.delay = -r.nextFloat() * 6000;
            stars.add(d);
        }
        for (int i = 0; i < 34; i++) {
            Dot d = new Dot();
            d.x = 60 + r.nextFloat() * 1480;
            d.y = 80 + r.nextFloat() * 860;
            d.kind = r.nextInt(3);
            sporeSize(d);
            d.dur = r.nextBoolean() ? 6000 : 12000;
            d.delay = -r.nextFloat() * 12000;
            d.dx = -24 + r.nextFloat() * 48;
            d.dy = -30 + r.nextFloat() * 22;
            spores.add(d);
        }
        Random r3 = new Random(3);
        for (int i = 0; i < 40; i++) {  // motes drifting in the moonlight shaft of the house
            Dot d = new Dot();
            float t = r3.nextFloat();
            d.y = 80 + r3.nextFloat() * 800;
            d.x = 1050 - (1050 - 520) * (d.y / 905) + (-60 + r3.nextFloat() * 220) + t * 40;
            d.kind = r3.nextInt(3);
            sporeSize(d);
            d.dur = r3.nextBoolean() ? 6000 : 12000;
            d.delay = -r3.nextFloat() * 12000;
            d.dx = -30 + r3.nextFloat() * 60;
            d.dy = 10 + r3.nextFloat() * 30;
            dust.add(d);
        }
        for (int i = 0; i < 6; i++) puffSx[i] = -10 + r.nextFloat() * 20;

        starPaint = new Paint[4];
        for (int i = 0; i < 4; i++) starPaint[i] = dotPaint(starR[i] / 2, 0xf4f2dc, starR[i] / 2 + 1, 4, .7f, 0xf4f2dc);
        sporePaint = new Paint[]{dotPaint(1.5f, 0xf6e6a0, 3.5f, 6, .55f, 0xf6e6a0), dotPaint(1, 0xd9f2cf, 3, 5, .45f, 0xc8f0c8),
                radial(new int[]{argb(.8f, 255, 250, 230), argb(0, 255, 250, 230)}, new float[]{0, .99f})};

        twinkle = new Keys(Keys.EASE_IN_OUT, true).k(0, "op", 1).k(.5f, "op", .2f).k(1, "op", 1).done();
        sporeK = new Keys(Keys.EASE_IN_OUT, true).k(0, "tx", 0, "ty", 0, "op", .25f).k(.25f, "op", 1).k(.5f, "tx", 1, "ty", 1, "op", .6f)
                .k(.75f, "op", 1).k(1, "tx", 0, "ty", 0, "op", .25f).done();
        moonK = new Keys(Keys.EASE_IN_OUT, true).k(0, "op", .5f, "s", 1).k(.5f, "op", 1, "s", 1.05f).k(1, "op", .5f, "s", 1).done();
        shootK = new Keys(Keys.LINEAR, true).k(0, "rot", 18, "sx", .2f, "op", 0).k(.70f, "rot", 18, "sx", .2f, "op", 0).k(.71f, "op", 1)
                .k(.76f, "tx", 380, "ty", 125, "rot", 18, "sx", 1, "op", 0).k(1, "op", 0).done();
        puffK = new Keys(Keys.EASE_OUT, true).k(0, "tx", 0, "ty", 0, "s", .4f, "op", 0).k(.12f, "op", 1).k(1, "tx", 70, "ty", -170, "s", 3.2f, "op", 0).done();
        fallK = new Keys(Keys.LINEAR, true).k(0, "tx", 1380, "ty", -20, "rot", 0).k(.25f, "tx", 1300, "ty", 240, "rot", 160)
                .k(.5f, "tx", 1390, "ty", 520, "rot", 320).k(.75f, "tx", 1310, "ty", 790, "rot", 480).k(1, "tx", 1370, "ty", 1030, "rot", 640).done();
        flickerK = keys("flicker", new JSONObject());
        flameK = new Keys(Keys.EASE_IN_OUT, true).k(0, "s", 1).k(.25f, "sx", .82f, "sy", 1.3f, "skx", 7).k(.5f, "sx", 1.12f, "sy", .84f, "skx", -5)
                .k(.75f, "sx", .9f, "sy", 1.16f, "skx", 3).k(1, "s", 1).done();
        emberK = new Keys(Keys.EASE_OUT, true).k(0, "tx", 0, "ty", 0, "op", 0).k(.1f, "op", 1).k(1, "tx", 14, "ty", -60, "op", 0).done();
        float[] sx = {0, 4, -2, 6, 1, -3};
        for (int i = 0; i < 6; i++) {
            float x = sx[i], w = i % 2 == 0 ? 1 : -1;
            steamK[i] = new Keys(Keys.LINEAR, true).k(0, "tx", 0, "ty", 0, "sx", .4f, "sy", .5f, "op", 0).k(.08f, "op", .8f)
                    .k(.28f, "tx", x + 5, "ty", -20, "sx", .8f, "sy", 1.2f, "rot", w * 14)
                    .k(.52f, "tx", -x + 2, "ty", -44, "sx", 1.3f, "sy", 1.6f, "rot", w * -10, "op", .45f)
                    .k(.76f, "tx", x + 9, "ty", -70, "sx", 1.9f, "sy", 2, "rot", w * 8, "op", .2f)
                    .k(1, "tx", -x + 5, "ty", -96, "sx", 2.5f, "sy", 2.3f, "op", 0).done();
        }

        moonPaint = radial(new int[]{argb(.22f, 246, 242, 222), argb(.10f, 246, 242, 222), argb(0, 246, 242, 222)}, new float[]{0, .45f, .7f});
        shootPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        shootPaint.setShader(new LinearGradient(0, 0, 140, 0, argb(0, 255, 250, 225), argb(.95f, 255, 250, 225), Shader.TileMode.CLAMP));
        puffPaint = radial(new int[]{argb(.55f, 215, 212, 195), argb(0, 215, 212, 195)}, new float[]{0, .7f});
        emberPaint = dotPaint(1.5f, 0xffcf6a, 3.5f, 5, .8f, 0xff9632);
        steamPaint = radial(new int[]{argb(.6f, 242, 242, 234), argb(.3f, 242, 242, 234), argb(0, 242, 242, 234)}, new float[]{0, .45f, .85f});
        for (int i = 0; i < FLAMES.length; i++)
            flamePaint[i] = radial(new int[]{argb(.95f, 255, 244, 180), argb(.75f, 255, 170, 70), argb(0, 220, 80, 20)}, new float[]{0, .42f, .74f});
        glowWin = radial(new int[]{argb(.42f, 240, 170, 80), argb(0, 240, 170, 80)}, new float[]{0, 1});
        glowStove = radial(new int[]{argb(.5f, 255, 150, 60), argb(0, 255, 150, 60)}, new float[]{0, 1});
        screen.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.SCREEN));
        leaf.moveTo(0, -8);
        leaf.quadTo(6, -2, 0, 8);
        leaf.quadTo(-6, -2, 0, -8);
        leaf.close();
        leafPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        leafPaint.setColor(0xffb8742e);
        leafVein = new Paint(Paint.ANTI_ALIAS_FLAG);
        leafVein.setColor(0xff3a2614);
        leafVein.setStyle(Paint.Style.STROKE);
        leafVein.setStrokeWidth(.6f);
        shade = makeShade();
        vignette = makeVignette();
        Bitmap noise = makeNoise();
        grainPaint = new Paint(Paint.FILTER_BITMAP_FLAG);
        grainPaint.setShader(new BitmapShader(noise, Shader.TileMode.REPEAT, Shader.TileMode.REPEAT));
    }

    /** The room falls into shadow towards the sides; the stove, lamp and candle keep their light. */
    private static Bitmap makeShade() {
        int w = 800, h = 500;
        float k = w / W;
        Bitmap b = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(b);
        c.drawColor(argb(.22f, 10, 6, 3));
        Paint p = new Paint();
        p.setShader(new LinearGradient(0, 0, 0, h, new int[]{argb(.35f, 6, 3, 2), argb(0, 6, 3, 2), argb(0, 6, 3, 2), argb(.45f, 6, 3, 2)},
                new float[]{0, .3f, .75f, 1}, Shader.TileMode.CLAMP));
        c.drawRect(0, 0, w, h, p);
        p.setShader(new LinearGradient(0, 0, w, 0, new int[]{argb(.88f, 6, 3, 2), argb(.55f, 6, 3, 2), argb(.12f, 6, 3, 2), argb(.12f, 6, 3, 2), argb(.55f, 6, 3, 2), argb(.88f, 6, 3, 2)},
                new float[]{0, .09f, .24f, .76f, .91f, 1}, Shader.TileMode.CLAMP));
        c.drawRect(0, 0, w, h, p);
        float[][] holes = {{1305, 745, .25f, 90, 300}, {800, 460, .35f, 0, 260}, {942, 722, .45f, 0, 150}};
        Paint mp = new Paint();
        mp.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.DST_IN));
        for (float[] hl : holes) {
            float r = hl[4] * k;
            mp.setShader(new RadialGradient(hl[0] * k, hl[1] * k, r, new int[]{argb(hl[2], 0, 0, 0), argb(hl[2], 0, 0, 0), 0xff000000},
                    new float[]{0, hl[3] / hl[4], 1}, Shader.TileMode.CLAMP));
            c.drawRect(0, 0, w, h, mp);
        }
        return b;
    }

    private static Bitmap makeVignette() {
        int w = 800, h = 500;
        Bitmap b = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(b);
        Paint p = new Paint();
        Matrix lm = new Matrix();
        RadialGradient warm = new RadialGradient(0, 0, 1, argb(.08f, 243, 210, 122), argb(0, 243, 210, 122), Shader.TileMode.CLAMP);
        lm.setScale(.4f * w, .4f * h);
        lm.postTranslate(.5f * w, .55f * h);
        warm.setLocalMatrix(lm);
        p.setShader(warm);
        c.drawRect(0, 0, w, h, p);
        RadialGradient vig = new RadialGradient(0, 0, 1, new int[]{argb(0, 5, 17, 15), argb(0, 5, 17, 15), argb(.55f, 5, 17, 15)},
                new float[]{0, .55f, 1}, Shader.TileMode.CLAMP);
        lm.setScale(.75f * w, .75f * h);
        lm.postTranslate(.52f * w, .5f * h);
        vig.setLocalMatrix(lm);
        p.setShader(vig);
        c.drawRect(0, 0, w, h, p);
        return b;
    }

    private static Bitmap makeNoise() {
        Random r = new Random(7);
        int n = 256;
        int[] px = new int[n * n];
        for (int i = 0; i < px.length; i++) {
            double a = Math.max(0, Math.min(1, .5 + r.nextGaussian() * .22));
            int al = (int) Math.min(255, a * .09 * 255 * 2);
            px[i] = (al << 24) | (115 << 16) | (102 << 8) | 77;
        }
        return Bitmap.createBitmap(px, n, n, Bitmap.Config.ARGB_8888);
    }

    /** A unit radial-gradient paint drawn as an ellipse of radii rx, ry around (cx, cy). */
    private static void glowAt(Canvas c, Paint p, float cx, float cy, float rx, float ry, float alpha) {
        if (alpha <= 0.004f || rx <= 0 || ry <= 0) return;
        p.setAlpha(Math.round(Math.min(1, alpha) * 255));
        c.save();
        c.translate(cx, cy);
        c.scale(rx, ry);
        c.drawCircle(0, 0, 1, p);
        c.restore();
    }

    private void drawDots(Canvas c, List<Dot> dots, Paint[] paints, Keys k, boolean move) {
        for (Dot d : dots) {
            k.sample(loop(ms, d.delay, d.dur), s);
            float x = d.x + d.off + (move ? s[Keys.TX] * d.dx : 0), y = d.y + d.off + (move ? s[Keys.TY] * d.dy : 0);
            glowAt(c, paints[d.kind], x, y, d.r, d.r, s[Keys.OP]);
        }
    }

    private float fxOr(String id, int prop, float def) {
        Fx f = extraFx.get(id);
        if (f == null) return def;
        f.k.sample(f.x(), s2);
        return s2[prop];
    }

    private void drawExtra(Canvas c, String kind) {
        switch (kind) {
            case "moonglow": {
                moonK.sample(loop(ms, 0, 12000), s);
                float r = 230 * 1.4142f * s[Keys.SX];
                glowAt(c, moonPaint, 1260, 230, r, r, s[Keys.OP]);
                break;
            }
            case "stars":
                drawDots(c, stars, starPaint, twinkle, false);
                break;
            case "shoot": {
                shootK.sample(loop(ms, 0, 12000), s);
                if (s[Keys.OP] < .01f) break;
                c.save();
                m.reset();
                Keys.transform(m, s, 320, 60.8f);
                c.concat(m);
                shootPaint.setAlpha(Math.round(s[Keys.OP] * 255));
                c.drawRoundRect(180, 60, 320, 61.6f, 1, 1, shootPaint);
                c.restore();
                break;
            }
            case "puffs":
                for (int i = 0; i < 6; i++) {
                    puffK.sample(loop(ms, -i * 1000, 6000), s);
                    float px = (i % 2 == 1 ? 624 : 648) + 11, py = 324 + 11;
                    float tx = s[Keys.TX] / 70 * (70 + puffSx[i]);
                    float rr = 15.6f * s[Keys.SX];
                    glowAt(c, puffPaint, px + tx, py + s[Keys.TY], rr, rr, s[Keys.OP]);
                }
                break;
            case "spores":
                drawDots(c, spores, sporePaint, sporeK, true);
                break;
            case "dust":
                drawDots(c, dust, sporePaint, sporeK, true);
                break;
            case "fall": {
                fallK.sample(loop(ms, 0, 12000), s);
                c.save();
                c.translate(s[Keys.TX] + 9, s[Keys.TY] + 9);
                c.rotate(s[Keys.ROT]);
                c.scale(.9f, .9f);
                c.drawPath(leaf, leafPaint);
                c.drawLine(0, -7, 0, 10, leafVein);
                c.restore();
                break;
            }
            case "firebox": {
                c.save();
                c.clipRect(1264, 708, 1346, 788);
                for (int i = 0; i < FLAMES.length; i++) {
                    float[] f = FLAMES[i];
                    flameK.sample(loop(ms, f[4], f[3]), s);
                    float l = 1264 + f[0], wd = f[1], ht = f[2], bot = 708 + 88;
                    c.save();
                    m.reset();
                    Keys.transform(m, s, l + wd / 2, bot);
                    c.concat(m);
                    Paint p = flamePaint[i];
                    p.setXfermode(screen.getXfermode());
                    // the gradient centre sits low in the tongue (50% 85%); the oval is the rounded flame body
                    c.clipPath(oval(l, bot - ht, l + wd, bot));
                    glowAt(c, p, l + wd / 2, bot - ht * .15f, wd / 2 * 1.4142f, ht * .85f * 1.4142f, .7f);
                    c.restore();
                }
                for (float[] e : EMBERS) {
                    emberK.sample(loop(ms, e[1], 2400), s);
                    emberPaint.setXfermode(screen.getXfermode());
                    glowAt(c, emberPaint, 1264 + e[0] + 1.5f + s[Keys.TX], 708 + 66 + 1.5f + s[Keys.TY], 8.5f, 8.5f, s[Keys.OP] * .7f);
                }
                c.restore();
                break;
            }
            case "steam":
                for (int i = 0; i < 6; i++) {
                    steamK[i].sample(loop(ms, -i * 430, 2600), s);
                    if (s[Keys.OP] < .01f) continue;
                    c.save();
                    m.reset();
                    Keys.transform(m, s, 1364.5f, 567);
                    c.concat(m);
                    float rx = 4.5f * 1.4142f, ry = 7.5f * 1.4142f;
                    glowAt(c, steamPaint, 1364.5f, 562.5f, rx, ry, s[Keys.OP]);
                    c.restore();
                }
                break;
            case "shade":
                bmpPaint.setAlpha(255);
                c.drawBitmap(shade, null, stageRect, bmpPaint);
                break;
            case "grain":
                bmpPaint.setAlpha(255);
                c.drawBitmap(vignette, null, stageRect, bmpPaint);
                c.drawRect(0, 0, W, H, grainPaint);
                break;
            default:
                if (kind.startsWith("glow:")) {
                    String id = kind.substring(5);
                    float[] b = extraBoxes.get(id);
                    flickerK.sample(loop(ms, b[4], 3000), s);
                    float a = s[Keys.OP] * fxOr(id, Keys.OP, 1), sc = fxOr(id, Keys.SX, 1);
                    Paint p = id.equals("stoveglow") ? glowStove : glowWin;
                    p.setXfermode(screen.getXfermode());
                    glowAt(c, p, b[0] + b[2] / 2, b[1] + b[3] / 2, b[2] / 2 * sc, b[3] / 2 * sc, a);
                }
        }
    }
}
