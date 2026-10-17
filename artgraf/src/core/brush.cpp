#include "brush.h"

#include <cmath>
#include <map>

namespace ag {

namespace {

constexpr int kTipRes = 128;
constexpr float kPi = 3.14159265f;

float sat(float v) { return v < 0 ? 0 : v > 1 ? 1 : v; }
float smooth(float e0, float e1, float x) {
    float t = sat((x - e0) / (e1 - e0));
    return t * t * (3 - 2 * t);
}
uint32_t hash(uint32_t x) {
    x ^= x >> 16; x *= 0x7feb352d; x ^= x >> 15; x *= 0x846ca68b; x ^= x >> 16;
    return x;
}
float hashf(int x, int y, int s = 0) { return (hash(uint32_t(x) * 73856093u ^ uint32_t(y) * 19349663u ^ uint32_t(s) * 83492791u) & 0xffffff) / float(0xffffff); }

// Value noise for grain, 0..1
float vnoise(float x, float y, int seed) {
    int xi = int(std::floor(x)), yi = int(std::floor(y));
    float fx = x - xi, fy = y - yi;
    fx = fx * fx * (3 - 2 * fx);
    fy = fy * fy * (3 - 2 * fy);
    float a = hashf(xi, yi, seed), b = hashf(xi + 1, yi, seed), c = hashf(xi, yi + 1, seed), d = hashf(xi + 1, yi + 1, seed);
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
}

using Field = float (*)(float u, float v);

// Each field maps tip space u,v ∈ [-1,1] to coverage 0..1.
float fSquare(float u, float v) { return std::max(std::fabs(u), std::fabs(v)) <= 0.92f ? 1.f : 0.f; }
float fChalk(float u, float v) {
    float d = std::sqrt(u * u + v * v);
    float edge = 0.8f + 0.12f * vnoise(std::atan2(v, u) * 3 + 10, 0, 7);
    if (d > edge) return 0;
    float grain = vnoise(u * 22 + 50, v * 22 + 50, 3) * 0.6f + vnoise(u * 60, v * 60, 4) * 0.4f;
    return grain > 0.42f ? 1.f : 0.f;
}
float fCharcoal(float u, float v) {
    float th = std::atan2(v, u), d = std::sqrt(u * u + v * v);
    float edge = 0.72f + 0.18f * vnoise(th * 2.2f + 5, 1, 11) + 0.08f * std::sin(th * 7);
    if (d > edge) return 0;
    float g = vnoise(u * 40, v * 40, 13);
    return sat((g - 0.25f) * 2.5f) * smooth(edge, edge - 0.15f, d);
}
float fSpray(float u, float v) {
    float best = 0;
    for (int i = 0; i < 90; i++) {
        float r = std::sqrt(hashf(i, 1, 21)) * 0.95f, a = hashf(i, 2, 21) * 2 * kPi;
        float cx = std::cos(a) * r, cy = std::sin(a) * r, rad = 0.015f + 0.035f * hashf(i, 3, 21);
        float d = std::hypot(u - cx, v - cy);
        best = std::max(best, smooth(rad, rad * 0.4f, d));
    }
    return best;
}
float fStar(float u, float v) {
    float th = std::atan2(u, -v), d = std::sqrt(u * u + v * v);
    float k = std::fmod(th + 2 * kPi, 2 * kPi / 5) / (2 * kPi / 5);  // 0..1 per arm
    float r = 0.42f + (0.95f - 0.42f) * std::pow(std::fabs(1 - 2 * k), 1.6f);
    return d <= r ? 1.f : 0.f;
}
float fLeaf(float u, float v) {
    float w = 0.42f * (1 - u * u);
    if (std::fabs(u) > 0.95f || std::fabs(v) > w) return 0;
    if (std::fabs(v) < 0.02f && u > -0.85f) return 0.35f;  // midrib
    return 1;
}
float fGrass(float u, float v) {
    // Tapered blade from bottom (v=1) to tip (v=-1), slightly curved.
    float t = (v + 1) * 0.5f;  // 0 tip .. 1 base
    float cx = 0.25f * (1 - t) * (1 - t);
    float w = 0.02f + 0.13f * t;
    return std::fabs(u - cx) <= w ? 1.f : 0.f;
}
float fBristle(float u, float v) {
    float best = 0;
    for (int i = 0; i < 16; i++) {
        float cx = -0.9f + 1.8f * (i + hashf(i, 5, 31) * 0.6f) / 16.f;
        float cy = (hashf(i, 6, 31) - 0.5f) * 0.25f;
        float rad = 0.04f + 0.05f * hashf(i, 7, 31);
        best = std::max(best, smooth(rad, rad * 0.5f, std::hypot(u - cx, v - cy)) * (0.6f + 0.4f * hashf(i, 8, 31)));
    }
    return best;
}
float fHeart(float u, float v) {
    float x = u * 1.25f, y = -v * 1.25f + 0.2f;
    float a = x * x + y * y - 1;
    return a * a * a - x * x * y * y * y <= 0 ? 1.f : 0.f;
}
float fCloud(float u, float v) {
    float acc = 0;
    for (int i = 0; i < 7; i++) {
        float cx = (hashf(i, 1, 41) - 0.5f) * 0.9f, cy = (hashf(i, 2, 41) - 0.5f) * 0.6f;
        float rad = 0.3f + 0.25f * hashf(i, 3, 41);
        acc = std::max(acc, smooth(rad, 0.f, std::hypot(u - cx, v - cy)));
    }
    return acc * (0.75f + 0.25f * vnoise(u * 8, v * 8, 43));
}
float fSplatter(float u, float v) {
    float best = smooth(0.45f, 0.40f, std::hypot(u, v) * (1 + 0.25f * std::sin(std::atan2(v, u) * 6)));
    for (int i = 0; i < 18; i++) {
        float r = 0.5f + 0.45f * hashf(i, 1, 51), a = hashf(i, 2, 51) * 2 * kPi;
        float rad = 0.03f + 0.07f * hashf(i, 3, 51);
        best = std::max(best, smooth(rad, rad * 0.7f, std::hypot(u - std::cos(a) * r, v - std::sin(a) * r)));
    }
    return best;
}

BrushTip rasterize(Field f) {
    BrushTip t;
    t.size = kTipRes;
    t.a.resize(size_t(kTipRes) * kTipRes);
    const int ss = 3;  // supersampling
    for (int y = 0; y < kTipRes; y++)
        for (int x = 0; x < kTipRes; x++) {
            float acc = 0;
            for (int j = 0; j < ss; j++)
                for (int i = 0; i < ss; i++) {
                    float u = ((x + (i + 0.5f) / ss) / kTipRes) * 2 - 1;
                    float v = ((y + (j + 0.5f) / ss) / kTipRes) * 2 - 1;
                    acc += f(u, v);
                }
            t.a[size_t(y) * kTipRes + x] = clamp8(acc / (ss * ss) * 255);
        }
    return t;
}

float tipSample(const BrushTip& t, float u, float v) {  // u,v in [-1,1]
    float fx = (u + 1) * 0.5f * t.size - 0.5f, fy = (v + 1) * 0.5f * t.size - 0.5f;
    int x0 = int(std::floor(fx)), y0 = int(std::floor(fy));
    float ax = fx - x0, ay = fy - y0;
    auto at = [&](int x, int y) -> float {
        if (x < 0 || y < 0 || x >= t.size || y >= t.size) return 0.f;
        return t.at(x, y) / 255.f;
    };
    float a = at(x0, y0), b = at(x0 + 1, y0), c = at(x0, y0 + 1), d = at(x0 + 1, y0 + 1);
    return a + (b - a) * ax + (c - a) * ay + (a - b - c + d) * ax * ay;
}

}  // namespace

const BrushTip& tipFor(TipShape shape, float) {
    static std::map<int, BrushTip> cache;
    auto it = cache.find(int(shape));
    if (it != cache.end()) return it->second;
    Field f = fSquare;
    switch (shape) {
        case TipShape::Square: f = fSquare; break;
        case TipShape::Chalk: f = fChalk; break;
        case TipShape::Charcoal: f = fCharcoal; break;
        case TipShape::Spray: f = fSpray; break;
        case TipShape::Star: f = fStar; break;
        case TipShape::Leaf: f = fLeaf; break;
        case TipShape::Grass: f = fGrass; break;
        case TipShape::Bristle: f = fBristle; break;
        case TipShape::Heart: f = fHeart; break;
        case TipShape::Cloud: f = fCloud; break;
        case TipShape::Splatter: f = fSplatter; break;
        default: break;
    }
    return cache.emplace(int(shape), rasterize(f)).first->second;
}

BrushTip tipFromImage(const Image& img) {
    BrushTip t;
    if (!img.valid()) return t;
    int s = std::max(img.w, img.h);
    Image sq(s, s);
    sq.blit(img, (s - img.w) / 2, (s - img.h) / 2);
    if (s > 256) {
        sq = sq.resized(256, 256);
        s = 256;
    }
    t.size = s;
    t.a.resize(size_t(s) * s);
    bool hasAlpha = false;
    for (size_t i = 3; i < sq.px.size(); i += 4) hasAlpha |= sq.px[i] < 250;
    for (int y = 0; y < s; y++)
        for (int x = 0; x < s; x++) {
            const uint8_t* p = sq.at(x, y);
            float lum = (p[0] * 0.299f + p[1] * 0.587f + p[2] * 0.114f) / 255.f;
            float a = p[3] / 255.f;
            // Opaque image: dark pixels paint. With transparency: alpha paints.
            float c = hasAlpha ? a * (1 - lum * 0.5f) : (1 - lum);
            t.a[size_t(y) * s + x] = clamp8(c * 255);
        }
    return t;
}

void stampTip(Coverage& cov, const BrushTip& tip, float cx, float cy, float diameter, float angleDeg, float roundness,
              float alpha, bool buildup, bool antialias) {
    // Round brushes are evaluated analytically; `tip.size == 0` with hardness passed through `tip`
    // is handled by stampRound below. Here: bitmap tips.
    float r = std::max(0.5f, diameter * 0.5f);
    float ext = r * 1.42f + 1;
    Rect b = Rect{int(std::floor(cx - ext)), int(std::floor(cy - ext)), int(std::ceil(cx + ext)), int(std::ceil(cy + ext))}
                 .intersect({0, 0, cov.w, cov.h});
    if (b.empty() || alpha <= 0) return;
    cov.touched = cov.touched.unite(b);
    float a = angleDeg * kPi / 180.f, ca = std::cos(a), sa = std::sin(a);
    roundness = std::clamp(roundness, 0.05f, 1.f);
    for (int y = b.y0; y < b.y1; y++)
        for (int x = b.x0; x < b.x1; x++) {
            float dx = x + 0.5f - cx, dy = y + 0.5f - cy;
            float u = (dx * ca + dy * sa) / r, v = (-dx * sa + dy * ca) / (r * roundness);
            if (u < -1 || u > 1 || v < -1 || v > 1) continue;
            float c = tipSample(tip, u, v);
            if (!antialias) c = c >= 0.5f ? 1.f : 0.f;
            c *= alpha;
            if (c <= 0.002f) continue;
            if (buildup) cov.add(x, y, c);
            else cov.put(x, y, c);
        }
}

namespace {
void stampRound(Coverage& cov, float cx, float cy, float diameter, float hardness, float angleDeg, float roundness,
                float alpha, bool buildup, bool antialias) {
    float r = std::max(0.5f, diameter * 0.5f);
    Rect b = Rect{int(std::floor(cx - r - 1)), int(std::floor(cy - r - 1)), int(std::ceil(cx + r + 1)), int(std::ceil(cy + r + 1))}
                 .intersect({0, 0, cov.w, cov.h});
    if (b.empty() || alpha <= 0) return;
    cov.touched = cov.touched.unite(b);
    float a = angleDeg * kPi / 180.f, ca = std::cos(a), sa = std::sin(a);
    roundness = std::clamp(roundness, 0.05f, 1.f);
    hardness = sat(hardness);
    float inner = hardness;
    for (int y = b.y0; y < b.y1; y++)
        for (int x = b.x0; x < b.x1; x++) {
            float dx = x + 0.5f - cx, dy = y + 0.5f - cy;
            float u = dx * ca + dy * sa, v = (-dx * sa + dy * ca) / roundness;
            float dpx = std::sqrt(u * u + v * v);  // distance in px along the unsquashed axis
            float d = dpx / r;
            float c;
            if (!antialias) c = dpx <= r ? 1.f : 0.f;
            else if (hardness >= 0.99f) c = sat(r - dpx + 0.5f);
            else if (d <= inner) c = 1.f;
            else {
                float t = sat((d - inner) / (1 - inner));
                c = 1.f - t * t * (3.f - 2.f * t);
            }
            c *= alpha;
            if (c <= 0.002f) continue;
            if (buildup) cov.add(x, y, c);
            else cov.put(x, y, c);
        }
}
}  // namespace

Rect BrushStamper::dab(Coverage& cov, const BrushPreset& p, const BrushTip& tip, float x, float y, float dirDeg, float) {
    Rect before = cov.touched;
    cov.touched = {};
    for (int i = 0; i < std::max(1, p.count); i++) {
        float size = std::max(1.f, p.size * (1 - p.sizeJitter * uni()));
        float ang = p.angle + (p.followStroke ? dirDeg : 0.f) + p.angleJitter * 360.f * (uni() - 0.5f);
        float px = x, py = y;
        if (p.scatter > 0) {
            float d = (uni() * 2 - 1) * p.scatter * p.size;
            float along = (uni() * 2 - 1) * p.scatter * p.size * 0.3f;
            float rad = dirDeg * kPi / 180.f;
            px += -std::sin(rad) * d + std::cos(rad) * along;
            py += std::cos(rad) * d + std::sin(rad) * along;
        }
        float alpha = p.flow * (1 - p.flowJitter * uni());
        bool aa = !p.aliased;
        if (p.shape == TipShape::Round)
            stampRound(cov, px, py, size, p.hardness, ang, p.roundness, alpha, p.buildup, aa);
        else
            stampTip(cov, tip, px, py, size, ang, p.roundness, alpha, p.buildup, aa);
    }
    Rect touched = cov.touched;
    cov.touched = before.unite(touched);
    return touched;
}

const std::vector<BrushPreset>& builtinBrushes() {
    static const std::vector<BrushPreset> list = [] {
        std::vector<BrushPreset> v;
        auto add = [&](BrushPreset p) { v.push_back(std::move(p)); };
        BrushPreset p;
        p = {}; p.name = "Жёсткая круглая"; p.hardness = 1; p.size = 20; p.spacing = 0.1f; add(p);
        p = {}; p.name = "Мягкая круглая"; p.hardness = 0; p.size = 60; p.spacing = 0.08f; add(p);
        p = {}; p.name = "Круглая 80%"; p.hardness = 0.8f; p.size = 30; add(p);
        p = {}; p.name = "Аэрограф"; p.hardness = 0; p.size = 80; p.flow = 0.06f; p.buildup = true; p.spacing = 0.04f; add(p);
        p = {}; p.name = "Каллиграфия"; p.hardness = 0.95f; p.size = 30; p.roundness = 0.18f; p.angle = 45; p.spacing = 0.04f; add(p);
        p = {}; p.name = "Перо-маркер"; p.hardness = 0.9f; p.size = 24; p.roundness = 0.45f; p.angle = -30; p.flow = 0.5f; p.buildup = true; p.spacing = 0.06f; add(p);
        p = {}; p.name = "Квадратная"; p.shape = TipShape::Square; p.size = 24; p.spacing = 0.08f; add(p);
        p = {}; p.name = "Пиксель"; p.shape = TipShape::Square; p.size = 1; p.spacing = 0.5f; p.aliased = true; add(p);
        p = {}; p.name = "Мел"; p.shape = TipShape::Chalk; p.size = 36; p.spacing = 0.15f; p.angleJitter = 1; add(p);
        p = {}; p.name = "Уголь"; p.shape = TipShape::Charcoal; p.size = 30; p.spacing = 0.1f; p.angleJitter = 1; p.flowJitter = 0.4f; add(p);
        p = {}; p.name = "Сухая кисть"; p.shape = TipShape::Bristle; p.size = 50; p.spacing = 0.03f; p.followStroke = true; p.angle = 90; p.flow = 0.8f; add(p);
        p = {}; p.name = "Акварель"; p.shape = TipShape::Cloud; p.size = 70; p.flow = 0.12f; p.buildup = true; p.spacing = 0.1f; p.sizeJitter = 0.3f; p.angleJitter = 1; add(p);
        p = {}; p.name = "Распылитель"; p.shape = TipShape::Spray; p.size = 70; p.spacing = 0.25f; p.angleJitter = 1; p.sizeJitter = 0.3f; add(p);
        p = {}; p.name = "Кляксы"; p.shape = TipShape::Splatter; p.size = 60; p.spacing = 0.9f; p.scatter = 0.8f; p.sizeJitter = 0.6f; p.angleJitter = 1; add(p);
        p = {}; p.name = "Звёзды"; p.shape = TipShape::Star; p.size = 30; p.spacing = 1.3f; p.scatter = 1.5f; p.sizeJitter = 0.7f; p.angleJitter = 1; add(p);
        p = {}; p.name = "Листья"; p.shape = TipShape::Leaf; p.size = 44; p.spacing = 0.9f; p.scatter = 1.0f; p.sizeJitter = 0.5f; p.angleJitter = 1; add(p);
        p = {}; p.name = "Трава"; p.shape = TipShape::Grass; p.size = 70; p.spacing = 0.18f; p.scatter = 0.6f; p.sizeJitter = 0.5f; p.angleJitter = 0.06f; add(p);
        p = {}; p.name = "Сердечки"; p.shape = TipShape::Heart; p.size = 30; p.spacing = 1.4f; p.scatter = 1.0f; p.sizeJitter = 0.5f; p.angleJitter = 0.15f; add(p);
        p = {}; p.name = "Облака"; p.shape = TipShape::Cloud; p.size = 100; p.spacing = 0.3f; p.scatter = 0.6f; p.sizeJitter = 0.5f; p.angleJitter = 1; p.flow = 0.45f; add(p);
        return v;
    }();
    return list;
}

}  // namespace ag
