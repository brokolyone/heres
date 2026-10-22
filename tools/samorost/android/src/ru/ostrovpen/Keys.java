package ru.ostrovpen;

import android.graphics.Matrix;

import java.util.ArrayList;
import java.util.List;

/**
 * Keyframe tracks with the semantics of the web version: CSS animations ease every keyframe interval,
 * Web Animations ease the whole run. A keyframe that sets any transform function resets the others to identity.
 */
final class Keys {
    static final int TX = 0, TY = 1, ROT = 2, SX = 3, SY = 4, SKX = 5, SKY = 6, SA = 7, OP = 8, BR = 9, N = 10;
    static final String[] NAMES = {"tx", "ty", "rot", "sx", "sy", "skx", "sky", "sa", "op", "br"};
    static final float[] DEF = {0, 0, 0, 1, 1, 0, 0, 1, 1, 1};

    static final int LINEAR = 0, EASE_IN_OUT = 1, EASE_OUT = 2, EASE_IN = 3;

    final float[][] t = new float[N][];
    final float[][] v = new float[N][];
    final int ease;
    final boolean perSegment;

    Keys(int ease, boolean perSegment) {
        this.ease = ease;
        this.perSegment = perSegment;
    }

    static int prop(String name) {
        for (int i = 0; i < N; i++) if (NAMES[i].equals(name)) return i;
        throw new IllegalArgumentException(name);
    }

    static int easeOf(String css) {
        switch (css) {
            case "ease-in-out": return EASE_IN_OUT;
            case "ease-out": return EASE_OUT;
            case "ease-in": return EASE_IN;
            default: return LINEAR;
        }
    }

    // ---------------- easing ----------------
    static float ease(int e, float x) {
        switch (e) {
            case EASE_IN_OUT: return bezier(.42f, 0, .58f, 1, x);
            case EASE_OUT: return bezier(0, 0, .58f, 1, x);
            case EASE_IN: return bezier(.42f, 0, 1, 1, x);
            default: return x;
        }
    }

    private static float bezier(float x1, float y1, float x2, float y2, float x) {
        if (x <= 0) return 0;
        if (x >= 1) return 1;
        float u = x;
        for (int i = 0; i < 8; i++) {
            float bx = bz(x1, x2, u) - x, d = dbz(x1, x2, u);
            if (Math.abs(bx) < 1e-5f) break;
            if (Math.abs(d) < 1e-6f) break;
            u -= bx / d;
        }
        u = Math.max(0, Math.min(1, u));
        return bz(y1, y2, u);
    }

    private static float bz(float a, float b, float u) {
        float m = 1 - u;
        return 3 * m * m * u * a + 3 * m * u * u * b + u * u * u;
    }

    private static float dbz(float a, float b, float u) {
        float m = 1 - u;
        return 3 * m * m * a + 6 * m * u * (b - a) + 3 * u * u * (1 - b);
    }

    /** Smooth in-out used by the game's own tweens (quadratic). */
    static float quad(float k) {
        return k < .5f ? 2 * k * k : 1 - (float) Math.pow(-2 * k + 2, 2) / 2;
    }

    // ---------------- sampling ----------------
    boolean has(int p) {
        return t[p] != null;
    }

    /** Value of property p at progress x in [0,1] (unwarped). */
    float get(int p, float x) {
        float[] tt = t[p], vv = v[p];
        if (tt == null) return DEF[p];
        if (!perSegment) x = ease(ease, x);
        if (x <= tt[0]) return vv[0];
        int n = tt.length;
        if (x >= tt[n - 1]) return vv[n - 1];
        int i = 1;
        while (i < n - 1 && tt[i] < x) i++;
        float t0 = tt[i - 1], t1 = tt[i];
        float k = t1 > t0 ? (x - t0) / (t1 - t0) : 1;
        if (perSegment) k = ease(ease, k);
        return vv[i - 1] + (vv[i] - vv[i - 1]) * k;
    }

    /** Fills s[0..N) with every property at progress x. */
    void sample(float x, float[] s) {
        for (int p = 0; p < N; p++) s[p] = get(p, x);
    }

    boolean hasTransform() {
        for (int p = 0; p <= SA; p++) if (t[p] != null) return true;
        return false;
    }

    /** m = translate(o) · translate · rotate · scale · skew · scale-along(-18°) · translate(-o). */
    static void transform(Matrix m, float[] s, float ox, float oy) {
        m.preTranslate(ox + s[TX], oy + s[TY]);
        if (s[ROT] != 0) m.preRotate(s[ROT]);
        if (s[SX] != 1 || s[SY] != 1) m.preScale(s[SX], s[SY]);
        if (s[SKX] != 0 || s[SKY] != 0)
            m.preSkew((float) Math.tan(Math.toRadians(s[SKX])), (float) Math.tan(Math.toRadians(s[SKY])));
        if (s[SA] != 1) {
            m.preRotate(-18);
            m.preScale(s[SA], 1);
            m.preRotate(18);
        }
        m.preTranslate(-ox, -oy);
    }

    // ---------------- building ----------------
    private final List<float[]> offs = new ArrayList<>();
    private final List<Object[]> frames = new ArrayList<>();

    /** One keyframe: offset (or -1 for evenly spaced) and name/value pairs; "s" sets both scales. */
    Keys k(float off, Object... kv) {
        offs.add(new float[]{off});
        frames.add(kv);
        return this;
    }

    Keys done() {
        int n = frames.size();
        float[] o = new float[n];
        for (int i = 0; i < n; i++) o[i] = offs.get(i)[0];
        if (o[0] < 0) o[0] = 0;
        if (n > 1 && o[n - 1] < 0) o[n - 1] = 1;
        for (int i = 1; i < n - 1; i++) {
            if (o[i] >= 0) continue;
            int j = i;
            while (o[j] < 0) j++;
            float a = o[i - 1], b = o[j];
            for (int q = i; q < j; q++) o[q] = a + (b - a) * (q - i + 1) / (j - i + 1);
        }
        List<List<float[]>> pts = new ArrayList<>();
        for (int p = 0; p < N; p++) pts.add(null);
        for (int i = 0; i < n; i++) {
            Object[] kv = frames.get(i);
            float[] val = new float[N];
            boolean[] set = new boolean[N];
            boolean tf = false;
            for (int q = 0; q < kv.length; q += 2) {
                String name = (String) kv[q];
                float x = ((Number) kv[q + 1]).floatValue();
                if (name.equals("s")) {
                    val[SX] = val[SY] = x;
                    set[SX] = set[SY] = true;
                    tf = true;
                } else {
                    int p = prop(name);
                    val[p] = x;
                    set[p] = true;
                    if (p <= SA) tf = true;
                }
            }
            for (int p = 0; p < N; p++) {
                if (!set[p] && tf && p <= SA) {
                    val[p] = DEF[p];
                    set[p] = true;
                }
                if (!set[p]) continue;
                if (pts.get(p) == null) pts.set(p, new ArrayList<>());
                pts.get(p).add(new float[]{o[i], val[p]});
            }
        }
        for (int p = 0; p < N; p++) {
            List<float[]> l = pts.get(p);
            if (l == null) continue;
            if (l.get(0)[0] > 0) l.add(0, new float[]{0, DEF[p]});
            if (l.get(l.size() - 1)[0] < 1) l.add(new float[]{1, DEF[p]});
            t[p] = new float[l.size()];
            v[p] = new float[l.size()];
            for (int i = 0; i < l.size(); i++) {
                t[p][i] = l.get(i)[0];
                v[p][i] = l.get(i)[1];
            }
        }
        offs.clear();
        frames.clear();
        return this;
    }
}
