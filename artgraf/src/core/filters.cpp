#include "filters.h"

#include <cmath>
#include <random>

namespace ag {

namespace {

void boxH(const float* src, float* dst, int w, int h, int r) {
    float inv = 1.f / float(2 * r + 1);
    for (int y = 0; y < h; y++) {
        const float* s = src + size_t(y) * w;
        float* d = dst + size_t(y) * w;
        float acc = s[0] * float(r + 1);
        for (int x = 1; x <= r; x++) acc += s[std::min(x, w - 1)];
        for (int x = 0; x < w; x++) {
            d[x] = acc * inv;
            acc += s[std::min(x + r + 1, w - 1)] - s[std::max(x - r, 0)];
        }
    }
}

void boxV(const float* src, float* dst, int w, int h, int r) {
    float inv = 1.f / float(2 * r + 1);
    for (int x = 0; x < w; x++) {
        float acc = src[x] * float(r + 1);
        for (int y = 1; y <= r; y++) acc += src[size_t(std::min(y, h - 1)) * w + x];
        for (int y = 0; y < h; y++) {
            dst[size_t(y) * w + x] = acc * inv;
            acc += src[size_t(std::min(y + r + 1, h - 1)) * w + x] - src[size_t(std::max(y - r, 0)) * w + x];
        }
    }
}

void rgb2hsl(float r, float g, float b, float& h, float& s, float& l) {
    float mx = std::max({r, g, b}), mn = std::min({r, g, b});
    l = (mx + mn) * 0.5f;
    if (mx == mn) { h = s = 0; return; }
    float d = mx - mn;
    s = l > 0.5f ? d / (2.f - mx - mn) : d / (mx + mn);
    if (mx == r) h = (g - b) / d + (g < b ? 6.f : 0.f);
    else if (mx == g) h = (b - r) / d + 2.f;
    else h = (r - g) / d + 4.f;
    h /= 6.f;
}

float hue2rgb(float p, float q, float t) {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1.f / 6) return p + (q - p) * 6 * t;
    if (t < 0.5f) return q;
    if (t < 2.f / 3) return p + (q - p) * (2.f / 3 - t) * 6;
    return p;
}

void hsl2rgb(float h, float s, float l, float& r, float& g, float& b) {
    if (s <= 0) { r = g = b = l; return; }
    float q = l < 0.5f ? l * (1 + s) : l + s - l * s;
    float p = 2 * l - q;
    r = hue2rgb(p, q, h + 1.f / 3);
    g = hue2rgb(p, q, h);
    b = hue2rgb(p, q, h - 1.f / 3);
}

template <class F>
void perPixel(Image& img, F f) {
    for (size_t i = 0; i < img.px.size(); i += 4) f(&img.px[i]);
}

void lut(Image& img, const uint8_t (&t)[256]) {
    perPixel(img, [&](uint8_t* p) { p[0] = t[p[0]]; p[1] = t[p[1]]; p[2] = t[p[2]]; });
}

// 3x3 convolution on color channels; alpha is preserved.
void convolve(Image& img, const float (&k)[9], float bias) {
    Image src = img;
    for (int y = 0; y < img.h; y++)
        for (int x = 0; x < img.w; x++) {
            float acc[3] = {bias, bias, bias};
            for (int j = -1; j <= 1; j++)
                for (int i = -1; i <= 1; i++) {
                    const uint8_t* p = src.at(std::clamp(x + i, 0, img.w - 1), std::clamp(y + j, 0, img.h - 1));
                    float kv = k[(j + 1) * 3 + (i + 1)];
                    acc[0] += p[0] * kv; acc[1] += p[1] * kv; acc[2] += p[2] * kv;
                }
            uint8_t* d = img.at(x, y);
            d[0] = clamp8(acc[0]); d[1] = clamp8(acc[1]); d[2] = clamp8(acc[2]);
        }
}

}  // namespace

void gaussianPlane(float* data, int w, int h, float radius) {
    int r = std::max(1, int(std::lround(radius)));
    std::vector<float> tmp(size_t(w) * h);
    for (int pass = 0; pass < 3; pass++) {
        boxH(data, tmp.data(), w, h, r);
        boxV(tmp.data(), data, w, h, r);
    }
}

void brightnessContrast(Image& img, float br, float ct) {
    float c = ct * 2.55f;
    float f = (259.f * (c + 255.f)) / (255.f * (259.f - c));
    uint8_t t[256];
    for (int i = 0; i < 256; i++) t[i] = clamp8((i - 128.f) * f + 128.f + br * 2.55f);
    lut(img, t);
}

void hueSaturation(Image& img, float hue, float sat, float light) {
    perPixel(img, [&](uint8_t* p) {
        float h, s, l;
        rgb2hsl(p[0] / 255.f, p[1] / 255.f, p[2] / 255.f, h, s, l);
        h += hue / 360.f;
        h -= std::floor(h);
        s = std::clamp(s * (1.f + sat / 100.f), 0.f, 1.f);
        if (light > 0) l += (1.f - l) * light / 100.f;
        else l *= 1.f + light / 100.f;
        float r, g, b;
        hsl2rgb(h, s, l, r, g, b);
        p[0] = clamp8(r * 255); p[1] = clamp8(g * 255); p[2] = clamp8(b * 255);
    });
}

void levels(Image& img, int inB, int inW, float gamma, int outB, int outW) {
    if (inW <= inB) inW = inB + 1;
    uint8_t t[256];
    for (int i = 0; i < 256; i++) {
        float v = std::clamp((i - inB) / float(inW - inB), 0.f, 1.f);
        v = std::pow(v, 1.f / std::max(0.01f, gamma));
        t[i] = clamp8(outB + v * (outW - outB));
    }
    lut(img, t);
}

void colorBalance(Image& img, float cr, float mg, float yb) {
    float k = 0.6f;  // full slider shifts a channel by ~150
    perPixel(img, [&](uint8_t* p) {
        // Weight toward midtones so whites and blacks stay put.
        float l = (p[0] + p[1] + p[2]) / 765.f;
        float wgt = 1.f - std::fabs(l - 0.5f) * 2.f * 0.6f;
        p[0] = clamp8(p[0] + cr * 2.55f * k * wgt);
        p[1] = clamp8(p[1] + mg * 2.55f * k * wgt);
        p[2] = clamp8(p[2] + yb * 2.55f * k * wgt);
    });
}

void autoContrast(Image& img) {
    int hist[3][256] = {};
    size_t n = 0;
    perPixel(img, [&](uint8_t* p) {
        if (p[3] < 8) return;
        hist[0][p[0]]++; hist[1][p[1]]++; hist[2][p[2]]++;
        n++;
    });
    if (!n) return;
    size_t clip = n / 200;  // ignore 0.5% outliers on each side
    uint8_t t[3][256];
    for (int c = 0; c < 3; c++) {
        int lo = 0, hi = 255;
        for (size_t acc = 0; lo < 255 && (acc += hist[c][lo]) <= clip;) lo++;
        for (size_t acc = 0; hi > 0 && (acc += hist[c][hi]) <= clip;) hi--;
        if (hi <= lo) { for (int i = 0; i < 256; i++) t[c][i] = uint8_t(i); continue; }
        for (int i = 0; i < 256; i++) t[c][i] = clamp8((i - lo) * 255.f / (hi - lo));
    }
    perPixel(img, [&](uint8_t* p) { p[0] = t[0][p[0]]; p[1] = t[1][p[1]]; p[2] = t[2][p[2]]; });
}

void invert(Image& img) {
    perPixel(img, [](uint8_t* p) { p[0] = 255 - p[0]; p[1] = 255 - p[1]; p[2] = 255 - p[2]; });
}

void desaturate(Image& img) {
    perPixel(img, [](uint8_t* p) {
        uint8_t v = clamp8(p[0] * 0.299f + p[1] * 0.587f + p[2] * 0.114f);
        p[0] = p[1] = p[2] = v;
    });
}

void sepia(Image& img) {
    perPixel(img, [](uint8_t* p) {
        float r = p[0], g = p[1], b = p[2];
        p[0] = clamp8(r * 0.393f + g * 0.769f + b * 0.189f);
        p[1] = clamp8(r * 0.349f + g * 0.686f + b * 0.168f);
        p[2] = clamp8(r * 0.272f + g * 0.534f + b * 0.131f);
    });
}

void posterize(Image& img, int n) {
    n = std::clamp(n, 2, 255);
    uint8_t t[256];
    for (int i = 0; i < 256; i++) t[i] = clamp8(std::round(i / 255.f * (n - 1)) * 255.f / (n - 1));
    lut(img, t);
}

void threshold(Image& img, int level) {
    perPixel(img, [&](uint8_t* p) {
        uint8_t v = (p[0] * 0.299f + p[1] * 0.587f + p[2] * 0.114f) >= level ? 255 : 0;
        p[0] = p[1] = p[2] = v;
    });
}

void gaussianBlur(Image& img, float radius) {
    if (radius < 0.5f || !img.valid()) return;
    size_t n = size_t(img.w) * img.h;
    std::vector<float> ch[4];
    for (auto& c : ch) c.resize(n);
    // Premultiply so transparent pixels don't bleed their (meaningless) color.
    for (size_t i = 0; i < n; i++) {
        const uint8_t* p = &img.px[i * 4];
        float a = p[3] / 255.f;
        ch[0][i] = p[0] * a; ch[1][i] = p[1] * a; ch[2][i] = p[2] * a; ch[3][i] = p[3];
    }
    for (auto& c : ch) gaussianPlane(c.data(), img.w, img.h, radius);
    for (size_t i = 0; i < n; i++) {
        uint8_t* p = &img.px[i * 4];
        float a = ch[3][i];
        float k = a > 0.01f ? 255.f / a : 0.f;
        p[0] = clamp8(ch[0][i] * k); p[1] = clamp8(ch[1][i] * k); p[2] = clamp8(ch[2][i] * k); p[3] = clamp8(a);
    }
}

void motionBlur(Image& img, float angleDeg, int dist) {
    if (dist < 1) return;
    Image src = img;
    float a = angleDeg * 3.14159265f / 180.f;
    float dx = std::cos(a), dy = -std::sin(a);
    int samples = dist * 2 + 1;
    for (int y = 0; y < img.h; y++)
        for (int x = 0; x < img.w; x++) {
            float acc[4] = {};
            for (int s = -dist; s <= dist; s++) {
                int sx = std::clamp(int(std::lround(x + dx * s)), 0, img.w - 1);
                int sy = std::clamp(int(std::lround(y + dy * s)), 0, img.h - 1);
                const uint8_t* p = src.at(sx, sy);
                float al = p[3];
                acc[0] += p[0] * al; acc[1] += p[1] * al; acc[2] += p[2] * al; acc[3] += al;
            }
            uint8_t* d = img.at(x, y);
            if (acc[3] > 0) {
                d[0] = clamp8(acc[0] / acc[3]); d[1] = clamp8(acc[1] / acc[3]); d[2] = clamp8(acc[2] / acc[3]);
            }
            d[3] = clamp8(acc[3] / samples);
        }
}

void unsharpMask(Image& img, float radius, float amount, int thr) {
    Image blurred = img;
    gaussianBlur(blurred, radius);
    float k = amount / 100.f;
    for (size_t i = 0; i < img.px.size(); i += 4)
        for (int c = 0; c < 3; c++) {
            int diff = int(img.px[i + c]) - int(blurred.px[i + c]);
            if (std::abs(diff) >= thr) img.px[i + c] = clamp8(img.px[i + c] + diff * k);
        }
}

void addNoise(Image& img, float amount, bool mono, uint32_t seed) {
    std::mt19937 rng(seed);
    std::normal_distribution<float> nd(0.f, amount * 1.28f);
    perPixel(img, [&](uint8_t* p) {
        if (mono) {
            float v = nd(rng);
            p[0] = clamp8(p[0] + v); p[1] = clamp8(p[1] + v); p[2] = clamp8(p[2] + v);
        } else {
            p[0] = clamp8(p[0] + nd(rng)); p[1] = clamp8(p[1] + nd(rng)); p[2] = clamp8(p[2] + nd(rng));
        }
    });
}

void pixelate(Image& img, int cell) {
    if (cell < 2) return;
    for (int by = 0; by < img.h; by += cell)
        for (int bx = 0; bx < img.w; bx += cell) {
            int ex = std::min(bx + cell, img.w), ey = std::min(by + cell, img.h);
            double acc[4] = {};
            for (int y = by; y < ey; y++)
                for (int x = bx; x < ex; x++) {
                    const uint8_t* p = img.at(x, y);
                    double a = p[3];
                    acc[0] += p[0] * a; acc[1] += p[1] * a; acc[2] += p[2] * a; acc[3] += a;
                }
            int n = (ex - bx) * (ey - by);
            RGBA c{};
            if (acc[3] > 0)
                c = {clamp8(float(acc[0] / acc[3])), clamp8(float(acc[1] / acc[3])), clamp8(float(acc[2] / acc[3])),
                     clamp8(float(acc[3] / n))};
            for (int y = by; y < ey; y++)
                for (int x = bx; x < ex; x++) img.set(x, y, c);
        }
}

void emboss(Image& img) {
    const float k[9] = {-2, -1, 0, -1, 1, 1, 0, 1, 2};
    convolve(img, k, 0);
    desaturate(img);
}

void findEdges(Image& img) {
    const float k[9] = {-1, -1, -1, -1, 8, -1, -1, -1, -1};
    convolve(img, k, 0);
    invert(img);
}

void vignette(Image& img, float amount) {
    float cx = img.w * 0.5f, cy = img.h * 0.5f;
    float maxd = std::sqrt(cx * cx + cy * cy);
    for (int y = 0; y < img.h; y++)
        for (int x = 0; x < img.w; x++) {
            float d = std::sqrt((x - cx) * (x - cx) + (y - cy) * (y - cy)) / maxd;
            float f = 1.f - amount / 100.f * std::pow(std::max(0.f, (d - 0.3f) / 0.7f), 1.6f);
            uint8_t* p = img.at(x, y);
            p[0] = clamp8(p[0] * f); p[1] = clamp8(p[1] * f); p[2] = clamp8(p[2] * f);
        }
}

void oilPaint(Image& img, int radius, int lv) {
    Image src = img;
    lv = std::clamp(lv, 2, 64);
    std::vector<int> cnt(lv), sr(lv), sg(lv), sb(lv);
    for (int y = 0; y < img.h; y++)
        for (int x = 0; x < img.w; x++) {
            std::fill(cnt.begin(), cnt.end(), 0);
            std::fill(sr.begin(), sr.end(), 0);
            std::fill(sg.begin(), sg.end(), 0);
            std::fill(sb.begin(), sb.end(), 0);
            for (int j = -radius; j <= radius; j++)
                for (int i = -radius; i <= radius; i++) {
                    const uint8_t* p = src.at(std::clamp(x + i, 0, img.w - 1), std::clamp(y + j, 0, img.h - 1));
                    int bin = (p[0] + p[1] + p[2]) * (lv - 1) / 765;
                    cnt[bin]++; sr[bin] += p[0]; sg[bin] += p[1]; sb[bin] += p[2];
                }
            int best = 0;
            for (int b = 1; b < lv; b++) if (cnt[b] > cnt[best]) best = b;
            uint8_t* d = img.at(x, y);
            d[0] = uint8_t(sr[best] / cnt[best]); d[1] = uint8_t(sg[best] / cnt[best]); d[2] = uint8_t(sb[best] / cnt[best]);
        }
}

void applyMasked(Image& img, const Image& filtered, const std::vector<uint8_t>& mask) {
    if (mask.empty()) { img = filtered; return; }
    for (size_t i = 0, n = size_t(img.w) * img.h; i < n; i++) {
        uint8_t m = mask[i];
        if (!m) continue;
        uint8_t* d = &img.px[i * 4];
        const uint8_t* s = &filtered.px[i * 4];
        if (m == 255) { d[0] = s[0]; d[1] = s[1]; d[2] = s[2]; d[3] = s[3]; continue; }
        for (int c = 0; c < 4; c++) d[c] = uint8_t(d[c] + (int(s[c]) - int(d[c])) * m / 255);
    }
}

}  // namespace ag
