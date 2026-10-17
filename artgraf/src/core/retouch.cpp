#include "retouch.h"

#include <cmath>

namespace ag {

namespace {

float sat(float v) { return v < 0 ? 0 : v > 1 ? 1 : v; }

float falloff(float d, float r, float hardness) {
    float t = d / r;
    if (t >= 1) return 0;
    if (t <= hardness) return 1;
    float k = (t - hardness) / std::max(1e-3f, 1 - hardness);
    return 1 - k * k * (3 - 2 * k);
}

void toHsl(float r, float g, float b, float& h, float& s, float& l) {
    float mx = std::max({r, g, b}), mn = std::min({r, g, b});
    l = (mx + mn) * 0.5f;
    if (mx == mn) { h = s = 0; return; }
    float d = mx - mn;
    s = l > 0.5f ? d / (2 - mx - mn) : d / (mx + mn);
    if (mx == r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (mx == g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h /= 6;
}
float hue2(float p, float q, float t) {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1.f / 6) return p + (q - p) * 6 * t;
    if (t < 0.5f) return q;
    if (t < 2.f / 3) return p + (q - p) * (2.f / 3 - t) * 6;
    return p;
}
void fromHsl(float h, float s, float l, float& r, float& g, float& b) {
    if (s <= 0) { r = g = b = l; return; }
    float q = l < 0.5f ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
    r = hue2(p, q, h + 1.f / 3); g = hue2(p, q, h); b = hue2(p, q, h - 1.f / 3);
}

}  // namespace

void Retoucher::begin(const Image& img, float x, float y, const RetouchParams& p) {
    if (p.mode != RetouchMode::Smudge) return;
    bufR = std::max(1, int(std::ceil(p.radius)));
    smudgeBuf = img.crop(Rect::of(int(x) - bufR, int(y) - bufR, bufR * 2 + 1, bufR * 2 + 1));
}

Rect Retoucher::dab(Image& img, float cx, float cy, const RetouchParams& p, const std::vector<uint8_t>& mask) {
    float r = std::max(1.f, p.radius);
    Rect b = Rect{int(std::floor(cx - r)), int(std::floor(cy - r)), int(std::ceil(cx + r)) + 1, int(std::ceil(cy + r)) + 1}
                 .intersect(img.bounds());
    if (b.empty()) return {};
    Image src = img.crop(b.expand(2));  // neighbourhood snapshot for blur/sharpen
    auto srcAt = [&](int x, int y) {
        x = std::clamp(x - (b.x0 - 2), 0, src.w - 1);
        y = std::clamp(y - (b.y0 - 2), 0, src.h - 1);
        return src.at(x, y);
    };
    int icx = int(cx), icy = int(cy);
    for (int y = b.y0; y < b.y1; y++)
        for (int x = b.x0; x < b.x1; x++) {
            float w = falloff(std::hypot(x + 0.5f - cx, y + 0.5f - cy), r, p.hardness) * p.strength;
            if (!mask.empty()) w *= mask[size_t(y) * img.w + x] / 255.f;
            if (w <= 0.001f) continue;
            uint8_t* px = img.at(x, y);
            switch (p.mode) {
                case RetouchMode::Blur:
                case RetouchMode::Sharpen: {
                    float acc[4] = {};
                    for (int j = -2; j <= 2; j++)
                        for (int i = -2; i <= 2; i++) {
                            const uint8_t* q = srcAt(x + i, y + j);
                            float a = q[3];
                            acc[0] += q[0] * a; acc[1] += q[1] * a; acc[2] += q[2] * a; acc[3] += a;
                        }
                    if (acc[3] <= 0) break;
                    float avg[3] = {acc[0] / acc[3], acc[1] / acc[3], acc[2] / acc[3]};
                    const uint8_t* o = srcAt(x, y);
                    for (int c = 0; c < 3; c++) {
                        float v = p.mode == RetouchMode::Blur ? o[c] + (avg[c] - o[c]) * w * 0.6f
                                                              : o[c] + (o[c] - avg[c]) * w * 0.8f;
                        px[c] = clamp8(v);
                    }
                    if (p.mode == RetouchMode::Blur) px[3] = clamp8(o[3] + (acc[3] / 25 - o[3]) * w * 0.6f);
                    break;
                }
                case RetouchMode::Smudge: {
                    int bx = x - icx + bufR, by = y - icy + bufR;
                    if (bx < 0 || by < 0 || bx >= smudgeBuf.w || by >= smudgeBuf.h) break;
                    uint8_t* q = smudgeBuf.at(bx, by);
                    RGBA mixed = lerp({px[0], px[1], px[2], px[3]}, {q[0], q[1], q[2], q[3]}, w * 0.9f);
                    px[0] = mixed.r; px[1] = mixed.g; px[2] = mixed.b; px[3] = mixed.a;
                    q[0] = mixed.r; q[1] = mixed.g; q[2] = mixed.b; q[3] = mixed.a;
                    break;
                }
                case RetouchMode::Dodge:
                case RetouchMode::Burn: {
                    float l = (px[0] * 0.299f + px[1] * 0.587f + px[2] * 0.114f) / 255.f;
                    float tone = p.range == 0 ? (1 - l) * (1 - l) : p.range == 2 ? l * l : 4 * l * (1 - l);
                    float k = w * tone * 0.18f;
                    for (int c = 0; c < 3; c++)
                        px[c] = p.mode == RetouchMode::Dodge ? clamp8(px[c] + (255 - px[c]) * k) : clamp8(px[c] * (1 - k));
                    break;
                }
                case RetouchMode::Sponge: {
                    float h, s, l;
                    toHsl(px[0] / 255.f, px[1] / 255.f, px[2] / 255.f, h, s, l);
                    s = sat(s + (p.saturate ? 1 : -1) * w * 0.12f * (p.saturate ? (1 - s) + 0.2f : s + 0.2f));
                    float rr, gg, bb;
                    fromHsl(h, s, l, rr, gg, bb);
                    px[0] = clamp8(rr * 255); px[1] = clamp8(gg * 255); px[2] = clamp8(bb * 255);
                    break;
                }
            }
        }
    return b;
}

namespace {

// Heals the hole pixels inside `tile`. Pixels of the region that are not healed yet (done == 0) are
// treated as unknown everywhere in the working box, so unhealed neighbours never act as a border.
Rect healTile(Image& img, const Coverage& region, Rect tile, Rect all, std::vector<uint8_t>& done,
              const std::vector<uint8_t>& selMask) {
    auto isHole = [&](int x, int y) {
        if (x < all.x0 || y < all.y0 || x >= all.x1 || y >= all.y1) return false;
        return region.at(x, y) > 0 && !done[size_t(y - all.y0) * all.w() + (x - all.x0)];
    };
    int margin = 3;
    Rect box = tile.expand(margin).intersect(img.bounds());
    int bw = box.w(), bh = box.h();
    std::vector<uint8_t> hole(size_t(bw) * bh);
    for (int y = 0; y < bh; y++)
        for (int x = 0; x < bw; x++) hole[size_t(y) * bw + x] = isHole(box.x0 + x, box.y0 + y);

    // Pick a nearby source offset whose surroundings best match the border of the hole.
    int span = std::max(tile.w(), tile.h()) + 4;
    int bestDx = span, bestDy = 0;
    double best = 1e300;
    for (int k = 0; k < 16; k++) {
        float a = k * 3.14159265f / 8;
        for (float dist : {1.0f, 1.6f, 2.4f}) {
            int dx = int(std::lround(std::cos(a) * span * dist)), dy = int(std::lround(std::sin(a) * span * dist));
            Rect sb = Rect{box.x0 + dx, box.y0 + dy, box.x1 + dx, box.y1 + dy};
            if (sb.intersect(img.bounds()).w() != bw || sb.intersect(img.bounds()).h() != bh) continue;
            double ssd = 0;
            int cnt = 0, bad = 0;
            for (int y = 0; y < bh; y += 2)
                for (int x = 0; x < bw; x += 2) {
                    int sx = box.x0 + x + dx, sy = box.y0 + y + dy;
                    if (isHole(sx, sy)) bad++;  // never copy from the area being healed
                    if (hole[size_t(y) * bw + x]) continue;
                    const uint8_t *t = img.at(box.x0 + x, box.y0 + y), *s = img.at(sx, sy);
                    for (int c = 0; c < 3; c++) ssd += double(t[c] - s[c]) * (t[c] - s[c]);
                    cnt++;
                }
            if (!cnt) continue;
            double score = ssd / cnt + bad * 4000.0;
            if (score < best) { best = score; bestDx = dx; bestDy = dy; }
        }
    }
    bool haveSource = best < 1e299;

    // Membrane: diffuse the target-minus-source difference from the border into the hole.
    std::vector<float> diff[3];
    for (auto& d : diff) d.assign(size_t(bw) * bh, 0.f);
    auto srcPx = [&](int x, int y) -> const uint8_t* {
        if (!haveSource) return img.at(box.x0 + x, box.y0 + y);
        return img.at(std::clamp(box.x0 + x + bestDx, 0, img.w - 1), std::clamp(box.y0 + y + bestDy, 0, img.h - 1));
    };
    for (int y = 0; y < bh; y++)
        for (int x = 0; x < bw; x++) {
            size_t i = size_t(y) * bw + x;
            if (hole[i]) continue;
            const uint8_t *t = img.at(box.x0 + x, box.y0 + y), *s = srcPx(x, y);
            for (int c = 0; c < 3; c++) diff[c][i] = float(t[c]) - (haveSource ? s[c] : 0.f);
        }
    for (int c = 0; c < 3; c++) {
        double sum = 0;
        int n = 0;
        for (size_t i = 0; i < hole.size(); i++) if (!hole[i]) { sum += diff[c][i]; n++; }
        float mean = n ? float(sum / n) : 0.f;
        for (size_t i = 0; i < hole.size(); i++) if (hole[i]) diff[c][i] = mean;
    }
    int iters = std::min(500, 40 + std::max(bw, bh) * 4);
    for (int it = 0; it < iters; it++)
        for (int y = 1; y < bh - 1; y++)
            for (int x = 1; x < bw - 1; x++) {
                size_t i = size_t(y) * bw + x;
                if (!hole[i]) continue;
                for (int c = 0; c < 3; c++)
                    diff[c][i] = 0.25f * (diff[c][i - 1] + diff[c][i + 1] + diff[c][i - bw] + diff[c][i + bw]);
            }
    for (int y = tile.y0; y < tile.y1; y++)
        for (int x = tile.x0; x < tile.x1; x++) {
            int lx = x - box.x0, ly = y - box.y0;
            size_t i = size_t(ly) * bw + lx;
            if (!hole[i]) continue;
            float w = region.at(x, y) / 255.f;
            if (!selMask.empty()) w *= selMask[size_t(y) * img.w + x] / 255.f;
            uint8_t* t = img.at(x, y);
            const uint8_t* s = srcPx(lx, ly);
            for (int c = 0; c < 3; c++) {
                float v = (haveSource ? s[c] : 0.f) + diff[c][i];
                t[c] = clamp8(t[c] + (v - t[c]) * w);
            }
            done[size_t(y - all.y0) * all.w() + (x - all.x0)] = 1;
        }
    return box;
}

}  // namespace

Rect healRegion(Image& img, const Coverage& region, const std::vector<uint8_t>& selMask) {
    Rect all = region.touched.intersect(img.bounds());
    if (all.empty()) return {};
    std::vector<uint8_t> done(size_t(all.w()) * all.h(), 0);
    // Long strokes are healed in tiles so each part gets its own nearby source texture.
    const int T = 72;
    Rect changed;
    for (int ty = all.y0; ty < all.y1; ty += T)
        for (int tx = all.x0; tx < all.x1; tx += T) {
            Rect tile = Rect{tx, ty, std::min(tx + T, all.x1), std::min(ty + T, all.y1)};
            bool any = false;
            for (int y = tile.y0; y < tile.y1 && !any; y++)
                for (int x = tile.x0; x < tile.x1; x++)
                    if (region.at(x, y)) { any = true; break; }
            if (any) changed = changed.unite(healTile(img, region, tile, all, done, selMask));
        }
    return changed;
}

}  // namespace ag
