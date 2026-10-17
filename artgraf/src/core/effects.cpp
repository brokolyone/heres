#include "effects.h"

#include <cmath>

#include "filters.h"
#include "parallel.h"

namespace ag {

namespace {

constexpr float kInf = 1e20f;
constexpr float kPi = 3.14159265f;
float sat(float v) { return v < 0 ? 0 : v > 1 ? 1 : v; }

// Felzenszwalb & Huttenlocher 1D squared distance transform.
void edt1d(const float* f, float* d, int n, std::vector<int>& v, std::vector<float>& z) {
    auto sect = [&](int q, int p) { return ((f[q] + float(q) * q) - (f[p] + float(p) * p)) / (2.f * q - 2.f * p); };
    int k = 0;
    v[0] = 0;
    z[0] = -kInf;
    z[1] = kInf;
    for (int q = 1; q < n; q++) {
        float s = sect(q, v[size_t(k)]);
        while (s <= z[size_t(k)]) {
            k--;
            s = sect(q, v[size_t(k)]);
        }
        k++;
        v[size_t(k)] = q;
        z[size_t(k)] = s;
        z[size_t(k) + 1] = kInf;
    }
    k = 0;
    for (int q = 0; q < n; q++) {
        while (z[size_t(k) + 1] < q) k++;
        int p = v[size_t(k)];
        d[q] = float(q - p) * float(q - p) + f[p];
    }
}

void blurPlane(std::vector<float>& p, int w, int h, float r) {
    if (r >= 1.f) gaussianPlane(p.data(), w, h, r / 3.f);  // "size" ≈ 3 sigma
}

void overPx(uint8_t* d, RGBA c, float a) {
    RGBA r = over({d[0], d[1], d[2], d[3]}, c, a);
    d[0] = r.r; d[1] = r.g; d[2] = r.b; d[3] = r.a;
}

}  // namespace

std::vector<float> distanceTransform(const std::vector<uint8_t>& inside, int w, int h) {
    size_t n = size_t(w) * h;
    std::vector<float> g(n);
    for (size_t i = 0; i < n; i++) g[i] = inside[i] ? 0.f : kInf;
    int m = std::max(w, h);
    // columns
    parallelRows(0, w, [&](int x0, int x1) {
        std::vector<float> f(static_cast<size_t>(m)), d(static_cast<size_t>(m)), z(static_cast<size_t>(m) + 1);
        std::vector<int> v(static_cast<size_t>(m));
        for (int x = x0; x < x1; x++) {
            for (int y = 0; y < h; y++) f[size_t(y)] = g[size_t(y) * w + x];
            edt1d(f.data(), d.data(), h, v, z);
            for (int y = 0; y < h; y++) g[size_t(y) * w + x] = d[size_t(y)];
        }
    });
    // rows
    parallelRows(0, h, [&](int y0, int y1) {
        std::vector<float> d(static_cast<size_t>(m)), z(static_cast<size_t>(m) + 1);
        std::vector<int> v(static_cast<size_t>(m));
        for (int y = y0; y < y1; y++) {
            float* row = &g[size_t(y) * w];
            edt1d(row, d.data(), w, v, z);
            for (int x = 0; x < w; x++) row[x] = std::sqrt(d[size_t(x)]);
        }
    });
    return g;
}

Image renderLayerFx(const Image& src, const LayerFx& fx) {
    int w = src.w, h = src.h;
    size_t n = size_t(w) * h;
    Image out(w, h);
    std::vector<float> A(n);
    std::vector<uint8_t> in(n), outside(n);
    for (size_t i = 0; i < n; i++) {
        A[i] = src.px[i * 4 + 3] / 255.f;
        in[i] = src.px[i * 4 + 3] >= 128;
        outside[i] = !in[i];
    }
    bool needOut = fx.dropShadow.on || fx.outerGlow.on || (fx.stroke.on && fx.stroke.position != 2);
    bool needIn = fx.innerGlow.on || (fx.stroke.on && fx.stroke.position != 0);
    std::vector<float> dOut, dIn;  // distance from outside pixels to the shape / inside pixels to the edge
    if (needOut) dOut = distanceTransform(in, w, h);
    if (needIn) dIn = distanceTransform(outside, w, h);

    // Spread grows the shape before blurring (used by shadow and glow).
    auto spreadAlpha = [&](float spreadPx) {
        std::vector<float> s(A);
        if (spreadPx > 0 && !dOut.empty())
            for (size_t i = 0; i < n; i++) s[i] = std::max(s[i], sat(spreadPx - dOut[i] + 0.5f));
        return s;
    };

    // 1. drop shadow
    if (fx.dropShadow.on) {
        const auto& s = fx.dropShadow;
        std::vector<float> sh = spreadAlpha(s.size * s.spread);
        blurPlane(sh, w, h, s.size * (1 - s.spread));
        float a = s.angle * kPi / 180.f;
        int dx = int(std::lround(-std::cos(a) * s.distance)), dy = int(std::lround(std::sin(a) * s.distance));
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++) {
                int sx = x - dx, sy = y - dy;
                if (sx < 0 || sy < 0 || sx >= w || sy >= h) continue;
                float v = sh[size_t(sy) * w + sx] * s.opacity;
                if (v > 0.002f) overPx(out.at(x, y), s.color, v);
            }
    }
    // 2. outer glow
    if (fx.outerGlow.on) {
        const auto& g = fx.outerGlow;
        std::vector<float> gl = spreadAlpha(g.size * std::max(0.15f, g.spread));
        blurPlane(gl, w, h, g.size);
        for (size_t i = 0; i < n; i++) {
            float v = sat(gl[i] * 1.6f) * g.opacity;
            if (v > 0.002f) overPx(&out.px[i * 4], g.color, v);
        }
    }

    // 3. layer pixels with fill effects
    Image body = src;
    if (fx.colorOverlay.on)
        for (size_t i = 0; i < n; i++) {
            uint8_t* p = &body.px[i * 4];
            RGBA c = lerp({p[0], p[1], p[2], p[3]}, {fx.colorOverlay.color.r, fx.colorOverlay.color.g, fx.colorOverlay.color.b, p[3]},
                          fx.colorOverlay.opacity);
            p[0] = c.r; p[1] = c.g; p[2] = c.b;
        }
    if (fx.gradientOverlay.on) {
        const auto& go = fx.gradientOverlay;
        Rect b = src.opaqueBounds();
        if (!b.empty()) {
            float cx = (b.x0 + b.x1) * 0.5f, cy = (b.y0 + b.y1) * 0.5f;
            float a = go.angle * kPi / 180.f;
            float ux = std::cos(a), uy = -std::sin(a);
            float half = (std::fabs(ux) * b.w() + std::fabs(uy) * b.h()) * 0.5f;
            if (go.type == GradientType::Radial || go.type == GradientType::Diamond) half = std::hypot(b.w(), b.h()) * 0.5f;
            float ax = go.type == GradientType::Linear || go.type == GradientType::Reflected ? cx - ux * half : cx;
            float ay = go.type == GradientType::Linear || go.type == GradientType::Reflected ? cy - uy * half : cy;
            float bx = cx + ux * half, by = cy + uy * half;
            for (int y = b.y0; y < b.y1; y++)
                for (int x = b.x0; x < b.x1; x++) {
                    uint8_t* p = body.at(x, y);
                    if (!p[3]) continue;
                    RGBA g = go.gradient.sample(gradientT(go.type, ax, ay, bx, by, x + 0.5f, y + 0.5f));
                    float k = go.opacity * g.a / 255.f;
                    p[0] = clamp8(p[0] + (g.r - p[0]) * k);
                    p[1] = clamp8(p[1] + (g.g - p[1]) * k);
                    p[2] = clamp8(p[2] + (g.b - p[2]) * k);
                }
        }
    }
    if (fx.innerGlow.on) {
        const auto& g = fx.innerGlow;
        for (size_t i = 0; i < n; i++) {
            uint8_t* p = &body.px[i * 4];
            if (!p[3]) continue;
            float e = sat(1 - dIn[i] / std::max(1.f, g.size)) * g.opacity;
            if (e <= 0) continue;
            p[0] = clamp8(p[0] + (g.color.r - p[0]) * e);
            p[1] = clamp8(p[1] + (g.color.g - p[1]) * e);
            p[2] = clamp8(p[2] + (g.color.b - p[2]) * e);
        }
    }
    if (fx.bevel.on) {
        const auto& bv = fx.bevel;
        std::vector<float> hgt(A);
        blurPlane(hgt, w, h, bv.size);
        float la = bv.angle * kPi / 180.f, alt = bv.altitude * kPi / 180.f;
        float lx = std::cos(la) * std::cos(alt), ly = -std::sin(la) * std::cos(alt), lz = std::sin(alt);
        float depth = bv.depth / 100.f * bv.size * 0.5f;
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++) {
                uint8_t* p = body.at(x, y);
                if (!p[3]) continue;
                auto H = [&](int xx, int yy) { return hgt[size_t(std::clamp(yy, 0, h - 1)) * w + std::clamp(xx, 0, w - 1)]; };
                float nx = -(H(x + 1, y) - H(x - 1, y)) * depth, ny = -(H(x, y + 1) - H(x, y - 1)) * depth, nz = 1;
                float len = std::sqrt(nx * nx + ny * ny + nz * nz);
                float shade = (nx * lx + ny * ly + nz * lz) / len - lz;  // 0 on flat areas
                if (shade > 0) {
                    float k = sat(shade * 2.5f) * bv.highlight;
                    p[0] = clamp8(p[0] + (255 - p[0]) * k); p[1] = clamp8(p[1] + (255 - p[1]) * k); p[2] = clamp8(p[2] + (255 - p[2]) * k);
                } else {
                    float k = sat(-shade * 2.5f) * bv.shadow;
                    p[0] = clamp8(p[0] * (1 - k)); p[1] = clamp8(p[1] * (1 - k)); p[2] = clamp8(p[2] * (1 - k));
                }
            }
    }
    for (size_t i = 0; i < n; i++) {
        const uint8_t* p = &body.px[i * 4];
        if (p[3]) overPx(&out.px[i * 4], {p[0], p[1], p[2], p[3]}, 1.f);
    }

    // 4. stroke on top
    if (fx.stroke.on) {
        const auto& st = fx.stroke;
        float s = st.size;
        for (size_t i = 0; i < n; i++) {
            float a = 0;
            if (in[i]) {
                if (st.position == 1) a = sat(s * 0.5f - dIn[i] + 0.5f);
                else if (st.position == 2) a = sat(s - dIn[i] + 0.5f);
                a *= A[i];
            } else {
                if (st.position == 0) a = sat(s - dOut[i] + 0.5f);
                else if (st.position == 1) a = sat(s * 0.5f - dOut[i] + 0.5f);
            }
            a *= st.opacity;
            if (a > 0.002f) overPx(&out.px[i * 4], st.color, a);
        }
    }
    return out;
}

}  // namespace ag
