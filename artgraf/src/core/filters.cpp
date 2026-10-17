#include "filters.h"

#include <cmath>
#include <random>

#include "parallel.h"

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

// ================================================================ extended set

namespace ag {

namespace {

constexpr float kPi = 3.14159265f;

// Bilinear sample with premultiplied alpha; outside the image returns transparent (or clamps).
RGBA sampleBilinear(const Image& img, float x, float y, bool clampEdge) {
    x -= 0.5f;
    y -= 0.5f;
    int x0 = int(std::floor(x)), y0 = int(std::floor(y));
    float fx = x - x0, fy = y - y0;
    float acc[4] = {};
    for (int j = 0; j < 2; j++)
        for (int i = 0; i < 2; i++) {
            int qx = x0 + i, qy = y0 + j;
            if (clampEdge) {
                qx = std::clamp(qx, 0, img.w - 1);
                qy = std::clamp(qy, 0, img.h - 1);
            } else if (qx < 0 || qy < 0 || qx >= img.w || qy >= img.h) {
                continue;
            }
            float w = (i ? fx : 1 - fx) * (j ? fy : 1 - fy);
            const uint8_t* p = img.at(qx, qy);
            float a = p[3] * w;
            acc[0] += p[0] * a; acc[1] += p[1] * a; acc[2] += p[2] * a; acc[3] += a;
        }
    if (acc[3] <= 0) return {};
    return {clamp8(acc[0] / acc[3]), clamp8(acc[1] / acc[3]), clamp8(acc[2] / acc[3]), clamp8(acc[3])};
}

// Inverse warp: f(x, y, sx&, sy&) gives the source position of destination pixel center (x, y).
template <class F>
void warp(Image& img, F f, bool clampEdge = true) {
    Image src = img;
    parallelRows(0, img.h, [&](int y0, int y1) {
        for (int y = y0; y < y1; y++)
            for (int x = 0; x < img.w; x++) {
                float sx, sy;
                f(x + 0.5f, y + 0.5f, sx, sy);
                img.set(x, y, sampleBilinear(src, sx, sy, clampEdge));
            }
    });
}

// Average of `samples` taps given by f(i) -> source position, premultiplied.
template <class F>
RGBA averageTaps(const Image& src, int samples, F f) {
    float acc[4] = {};
    for (int i = 0; i < samples; i++) {
        float sx, sy;
        f(i, sx, sy);
        RGBA c = sampleBilinear(src, sx, sy, true);
        float a = c.a;
        acc[0] += c.r * a; acc[1] += c.g * a; acc[2] += c.b * a; acc[3] += a;
    }
    if (acc[3] <= 0) return {};
    return {clamp8(acc[0] / acc[3]), clamp8(acc[1] / acc[3]), clamp8(acc[2] / acc[3]), clamp8(acc[3] / samples)};
}

float lum(const uint8_t* p) { return (p[0] * 0.299f + p[1] * 0.587f + p[2] * 0.114f) / 255.f; }

uint32_t hash32(uint32_t x) {
    x ^= x >> 16; x *= 0x7feb352d; x ^= x >> 15; x *= 0x846ca68b; x ^= x >> 16;
    return x;
}
float hashf(int x, int y, uint32_t s) { return (hash32(uint32_t(x) * 73856093u ^ uint32_t(y) * 19349663u ^ s * 83492791u) & 0xffffff) / float(0xffffff); }

float valueNoise(float x, float y, uint32_t seed) {
    int xi = int(std::floor(x)), yi = int(std::floor(y));
    float fx = x - xi, fy = y - yi;
    fx = fx * fx * (3 - 2 * fx);
    fy = fy * fy * (3 - 2 * fy);
    float a = hashf(xi, yi, seed), b = hashf(xi + 1, yi, seed), c = hashf(xi, yi + 1, seed), d = hashf(xi + 1, yi + 1, seed);
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
}

}  // namespace

void curveLut(const std::vector<std::pair<float, float>>& in, uint8_t out[256]) {
    std::vector<std::pair<float, float>> p = in;
    std::sort(p.begin(), p.end());
    if (p.empty()) p = {{0, 0}, {255, 255}};
    if (p.size() == 1) {
        for (int i = 0; i < 256; i++) out[i] = clamp8(p[0].second);
        return;
    }
    // Fritsch–Carlson monotone cubic interpolation.
    size_t n = p.size();
    std::vector<float> dx(n - 1), m(n - 1), t(n);
    for (size_t i = 0; i + 1 < n; i++) {
        dx[i] = std::max(1e-3f, p[i + 1].first - p[i].first);
        m[i] = (p[i + 1].second - p[i].second) / dx[i];
    }
    t[0] = m[0];
    t[n - 1] = m[n - 2];
    for (size_t i = 1; i + 1 < n; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) * 0.5f;
    for (size_t i = 0; i + 1 < n; i++) {
        if (m[i] == 0) { t[i] = t[i + 1] = 0; continue; }
        float a = t[i] / m[i], b = t[i + 1] / m[i], s = a * a + b * b;
        if (s > 9) {
            float k = 3 / std::sqrt(s);
            t[i] = k * a * m[i];
            t[i + 1] = k * b * m[i];
        }
    }
    for (int x = 0; x < 256; x++) {
        float fx = float(x);
        if (fx <= p.front().first) { out[x] = clamp8(p.front().second); continue; }
        if (fx >= p.back().first) { out[x] = clamp8(p.back().second); continue; }
        size_t i = 0;
        while (i + 2 < n && fx > p[i + 1].first) i++;
        float h = dx[i], u = (fx - p[i].first) / h;
        float h00 = (1 + 2 * u) * (1 - u) * (1 - u), h10 = u * (1 - u) * (1 - u), h01 = u * u * (3 - 2 * u), h11 = u * u * (u - 1);
        out[x] = clamp8(h00 * p[i].second + h10 * h * t[i] + h01 * p[i + 1].second + h11 * h * t[i + 1]);
    }
}

void applyLuts(Image& img, const uint8_t* r, const uint8_t* g, const uint8_t* b) {
    perPixel(img, [&](uint8_t* p) { p[0] = r[p[0]]; p[1] = g[p[1]]; p[2] = b[p[2]]; });
}

void vibrance(Image& img, float vib, float satAmt) {
    perPixel(img, [&](uint8_t* p) {
        float h, s, l;
        rgb2hsl(p[0] / 255.f, p[1] / 255.f, p[2] / 255.f, h, s, l);
        // Vibrance boosts muted colors more than saturated ones.
        s *= 1 + satAmt / 100.f;
        s += (vib / 100.f) * (1 - s) * s * 1.5f + (vib < 0 ? vib / 100.f * s * 0.5f : 0);
        s = std::clamp(s, 0.f, 1.f);
        float r, g, b;
        hsl2rgb(h, s, l, r, g, b);
        p[0] = clamp8(r * 255); p[1] = clamp8(g * 255); p[2] = clamp8(b * 255);
    });
}

void exposure(Image& img, float ev, float offset, float gamma) {
    uint8_t t[256];
    float k = std::pow(2.f, ev);
    for (int i = 0; i < 256; i++) {
        float v = std::pow(i / 255.f, 2.2f) * k + offset;  // operate in linear light
        v = std::pow(std::max(0.f, v), 1 / 2.2f);
        v = std::pow(std::clamp(v, 0.f, 1.f), 1 / std::max(0.01f, gamma));
        t[i] = clamp8(v * 255);
    }
    lut(img, t);
}

void photoFilter(Image& img, RGBA c, float density, bool keepLum) {
    float d = density / 100.f;
    perPixel(img, [&](uint8_t* p) {
        float l0 = lum(p);
        float r = p[0] * (1 - d) + p[0] * c.r / 255.f * d * 1.0f + c.r * d * 0.25f;
        float g = p[1] * (1 - d) + p[1] * c.g / 255.f * d * 1.0f + c.g * d * 0.25f;
        float b = p[2] * (1 - d) + p[2] * c.b / 255.f * d * 1.0f + c.b * d * 0.25f;
        if (keepLum) {
            float l1 = (r * 0.299f + g * 0.587f + b * 0.114f) / 255.f;
            if (l1 > 0.001f) { float k = l0 / l1; r *= k; g *= k; b *= k; }
        }
        p[0] = clamp8(r); p[1] = clamp8(g); p[2] = clamp8(b);
    });
}

void blackWhite(Image& img, float reds, float yellows, float greens, float cyans, float blues, float magentas) {
    // Weights per hue sector (percent, like the classic dialog); interpolated around the hue circle.
    float w[6] = {reds, yellows, greens, cyans, blues, magentas};
    perPixel(img, [&](uint8_t* p) {
        float h, s, l;
        rgb2hsl(p[0] / 255.f, p[1] / 255.f, p[2] / 255.f, h, s, l);
        float pos = h * 6.f;
        int i0 = int(std::floor(pos)) % 6, i1 = (i0 + 1) % 6;
        float f = pos - std::floor(pos);
        float weight = (w[i0] * (1 - f) + w[i1] * f) / 100.f;
        float base = lum(p);
        float v = base + (weight - 0.5f) * s * 0.8f;
        uint8_t g = clamp8(std::clamp(v, 0.f, 1.f) * 255);
        p[0] = p[1] = p[2] = g;
    });
}

void gradientMap(Image& img, const Gradient& g) {
    RGBA t[256];
    for (int i = 0; i < 256; i++) t[i] = g.sample(i / 255.f);
    perPixel(img, [&](uint8_t* p) {
        RGBA c = t[clamp8(lum(p) * 255)];
        p[0] = c.r; p[1] = c.g; p[2] = c.b;
    });
}

void channelMixer(Image& img, float rr, float rg, float rb, float gr, float gg, float gb, float br, float bg, float bb) {
    perPixel(img, [&](uint8_t* p) {
        float r = p[0], g = p[1], b = p[2];
        p[0] = clamp8((r * rr + g * rg + b * rb) / 100.f);
        p[1] = clamp8((r * gr + g * gg + b * gb) / 100.f);
        p[2] = clamp8((r * br + g * bg + b * bb) / 100.f);
    });
}

void zoomBlur(Image& img, float amount) {
    Image src = img;
    float cx = img.w * 0.5f, cy = img.h * 0.5f, k = amount / 100.f * 0.35f;
    const int S = 24;
    parallelRows(0, img.h, [&](int y0, int y1) {
        for (int y = y0; y < y1; y++)
            for (int x = 0; x < img.w; x++) {
                float dx = x + 0.5f - cx, dy = y + 0.5f - cy;
                img.set(x, y, averageTaps(src, S, [&](int i, float& sx, float& sy) {
                    float s = 1 - k * i / float(S - 1);
                    sx = cx + dx * s;
                    sy = cy + dy * s;
                }));
            }
    });
}

void spinBlur(Image& img, float angleDeg) {
    Image src = img;
    float cx = img.w * 0.5f, cy = img.h * 0.5f, a = angleDeg * kPi / 180.f;
    const int S = 24;
    parallelRows(0, img.h, [&](int y0, int y1) {
        for (int y = y0; y < y1; y++)
            for (int x = 0; x < img.w; x++) {
                float dx = x + 0.5f - cx, dy = y + 0.5f - cy;
                img.set(x, y, averageTaps(src, S, [&](int i, float& sx, float& sy) {
                    float t = a * (i / float(S - 1) - 0.5f), c = std::cos(t), s = std::sin(t);
                    sx = cx + dx * c - dy * s;
                    sy = cy + dx * s + dy * c;
                }));
            }
    });
}

void tiltShift(Image& img, float focusCenter, float focusSize, float blur) {
    Image blurred = img;
    gaussianBlur(blurred, blur);
    float c = focusCenter * img.h, half = focusSize * img.h * 0.5f, fade = img.h * 0.15f + 1;
    for (int y = 0; y < img.h; y++) {
        float d = std::fabs(y + 0.5f - c) - half;
        float k = std::clamp(d / fade, 0.f, 1.f);
        if (k <= 0) continue;
        for (int x = 0; x < img.w; x++) img.set(x, y, lerp(img.get(x, y), blurred.get(x, y), k));
    }
    vibrance(img, 25, 10);
}

void twirl(Image& img, float angleDeg) {
    float cx = img.w * 0.5f, cy = img.h * 0.5f, R = std::min(cx, cy), a = angleDeg * kPi / 180.f;
    warp(img, [&](float x, float y, float& sx, float& sy) {
        float dx = x - cx, dy = y - cy, d = std::sqrt(dx * dx + dy * dy);
        if (d >= R) { sx = x; sy = y; return; }
        float t = a * (1 - d / R) * (1 - d / R);
        float c = std::cos(t), s = std::sin(t);
        sx = cx + dx * c - dy * s;
        sy = cy + dx * s + dy * c;
    });
}

void spherize(Image& img, float amount) {
    float cx = img.w * 0.5f, cy = img.h * 0.5f, R = std::min(cx, cy), k = amount / 100.f;
    warp(img, [&](float x, float y, float& sx, float& sy) {
        float dx = (x - cx) / R, dy = (y - cy) / R, d = std::sqrt(dx * dx + dy * dy);
        if (d >= 1 || d <= 0) { sx = x; sy = y; return; }
        float nd = k >= 0 ? std::pow(d, 1 + k) : std::pow(d, 1 / (1 - k));
        float f = nd / d;
        sx = cx + dx * f * R;
        sy = cy + dy * f * R;
    });
}

void wave(Image& img, float amp, float len) {
    len = std::max(2.f, len);
    warp(img, [&](float x, float y, float& sx, float& sy) {
        sx = x + amp * std::sin(2 * kPi * y / len);
        sy = y + amp * std::sin(2 * kPi * x / len);
    });
}

void ripple(Image& img, float amount, float size) {
    float cx = img.w * 0.5f, cy = img.h * 0.5f;
    size = std::max(2.f, size);
    warp(img, [&](float x, float y, float& sx, float& sy) {
        float dx = x - cx, dy = y - cy, d = std::sqrt(dx * dx + dy * dy) + 1e-3f;
        float off = amount * std::sin(2 * kPi * d / size);
        sx = x + dx / d * off;
        sy = y + dy / d * off;
    });
}

void polarCoordinates(Image& img, bool toPolar) {
    float w = float(img.w), h = float(img.h), cx = w * 0.5f, cy = h * 0.5f, R = std::min(cx, cy);
    warp(img, [&](float x, float y, float& sx, float& sy) {
        if (toPolar) {
            float dx = x - cx, dy = y - cy;
            float ang = std::atan2(dx, -dy);
            if (ang < 0) ang += 2 * kPi;
            sx = ang / (2 * kPi) * w;
            sy = std::sqrt(dx * dx + dy * dy) / R * h;
        } else {
            float ang = x / w * 2 * kPi, r = y / h * R;
            sx = cx + std::sin(ang) * r;
            sy = cy - std::cos(ang) * r;
        }
    }, true);
}

void halftone(Image& img, int cell) {
    cell = std::max(3, cell);
    Image src = img;
    for (int y = 0; y < img.h; y++)
        for (int x = 0; x < img.w; x++) {
            uint8_t* p = img.at(x, y);
            p[0] = p[1] = p[2] = 255;
        }
    // Per-channel dots (CMY-ish) at different screen angles.
    const float angles[3] = {15, 75, 45};
    for (int ch = 0; ch < 3; ch++) {
        float a = angles[ch] * kPi / 180.f, ca = std::cos(a), sa = std::sin(a);
        for (int y = 0; y < img.h; y++)
            for (int x = 0; x < img.w; x++) {
                float u = (x * ca + y * sa) / cell, v = (-x * sa + y * ca) / cell;
                float fu = u - std::floor(u) - 0.5f, fv = v - std::floor(v) - 0.5f;
                // sample the cell center
                float cu = std::floor(u) + 0.5f, cv = std::floor(v) + 0.5f;
                int sx = std::clamp(int((cu * ca - cv * sa) * cell), 0, img.w - 1);
                int sy = std::clamp(int((cu * sa + cv * ca) * cell), 0, img.h - 1);
                float ink = 1 - src.at(sx, sy)[ch] / 255.f;
                float r = std::sqrt(ink) * 0.7f;
                float d = std::sqrt(fu * fu + fv * fv);
                float cov = std::clamp((r - d) * cell + 0.5f, 0.f, 1.f);
                uint8_t* p = img.at(x, y);
                p[ch] = clamp8(p[ch] * (1 - cov));
            }
    }
}

void glitch(Image& img, float shift, int slices, uint32_t seed) {
    Image src = img;
    std::mt19937 rng(seed);
    std::uniform_real_distribution<float> U(0, 1);
    for (int i = 0; i < slices; i++) {
        int y0 = int(U(rng) * img.h), hh = 2 + int(U(rng) * img.h / 12.f);
        int dx = int((U(rng) * 2 - 1) * shift);
        for (int y = y0; y < std::min(img.h, y0 + hh); y++)
            for (int x = 0; x < img.w; x++) {
                int sx = std::clamp(x - dx, 0, img.w - 1);
                img.set(x, y, src.get(sx, y));
            }
    }
    chromaticAberration(img, shift * 0.15f + 2);
}

void chromaticAberration(Image& img, float px) {
    Image src = img;
    int d = int(std::lround(px));
    for (int y = 0; y < img.h; y++)
        for (int x = 0; x < img.w; x++) {
            uint8_t* p = img.at(x, y);
            p[0] = src.at(std::clamp(x + d, 0, img.w - 1), y)[0];
            p[2] = src.at(std::clamp(x - d, 0, img.w - 1), y)[2];
        }
}

void renderClouds(Image& img, RGBA fg, RGBA bg, float scale, uint32_t seed) {
    float base = std::max(4.f, scale);
    parallelRows(0, img.h, [&](int y0, int y1) {
        for (int y = y0; y < y1; y++)
            for (int x = 0; x < img.w; x++) {
                float v = 0, amp = 0.5f, f = 1.f / base;
                for (int o = 0; o < 6; o++) {
                    v += amp * valueNoise(x * f, y * f, seed + uint32_t(o) * 101u);
                    amp *= 0.5f;
                    f *= 2.f;
                }
                RGBA c = lerp(bg, fg, std::clamp((v - 0.15f) / 0.7f, 0.f, 1.f));
                c.a = 255;
                img.set(x, y, c);
            }
    });
}

void lensFlare(Image& img, float cx, float cy, float brightness) {
    float k = brightness / 100.f;
    float ex = img.w * 0.5f, ey = img.h * 0.5f;
    struct Ghost { float t, r, a; uint8_t cr, cg, cb; };
    const Ghost ghosts[] = {{0.5f, 0.05f, 0.25f, 120, 200, 255}, {0.8f, 0.03f, 0.3f, 255, 160, 80},
                            {1.3f, 0.08f, 0.15f, 160, 255, 160}, {1.6f, 0.02f, 0.35f, 255, 120, 220},
                            {2.0f, 0.12f, 0.1f, 140, 160, 255}};
    float diag = std::hypot(img.w, img.h);
    parallelRows(0, img.h, [&](int y0, int y1) {
        for (int y = y0; y < y1; y++)
            for (int x = 0; x < img.w; x++) {
                uint8_t* p = img.at(x, y);
                float dx = x - cx, dy = y - cy, d = std::sqrt(dx * dx + dy * dy) / diag;
                float r = 0, g = 0, b = 0;
                float core = std::exp(-d * d * 900) * 1.2f + std::exp(-d * 18) * 0.35f;
                float ang = std::atan2(dy, dx);
                float rays = std::pow(std::fabs(std::cos(ang * 6)), 40) * std::exp(-d * 9) * 0.6f;
                r += (core + rays) * 255; g += (core + rays) * 240; b += (core + rays) * 220;
                float ring = std::exp(-std::pow((d - 0.09f) * 60, 2)) * 0.15f;
                r += ring * 180; g += ring * 120; b += ring * 255;
                for (const Ghost& gh : ghosts) {
                    float gx = cx + (ex - cx) * gh.t, gy = cy + (ey - cy) * gh.t;
                    float gd = std::hypot(x - gx, y - gy) / diag;
                    float v = std::clamp((gh.r - gd) / (gh.r * 0.15f), 0.f, 1.f) * gh.a;
                    r += v * gh.cr; g += v * gh.cg; b += v * gh.cb;
                }
                // screen blend
                p[0] = clamp8(255 - (255 - p[0]) * (1 - std::min(1.f, r * k / 255)));
                p[1] = clamp8(255 - (255 - p[1]) * (1 - std::min(1.f, g * k / 255)));
                p[2] = clamp8(255 - (255 - p[2]) * (1 - std::min(1.f, b * k / 255)));
            }
    });
}

void median(Image& img, int radius) {
    if (radius < 1) return;
    Image src = img;
    parallelRows(0, img.h, [&](int y0, int y1) {
        std::vector<uint8_t> v[3];
        for (int y = y0; y < y1; y++)
            for (int x = 0; x < img.w; x++) {
                for (auto& c : v) c.clear();
                for (int j = -radius; j <= radius; j++)
                    for (int i = -radius; i <= radius; i++) {
                        const uint8_t* p = src.at(std::clamp(x + i, 0, img.w - 1), std::clamp(y + j, 0, img.h - 1));
                        v[0].push_back(p[0]); v[1].push_back(p[1]); v[2].push_back(p[2]);
                    }
                uint8_t* d = img.at(x, y);
                for (int c = 0; c < 3; c++) {
                    auto mid = v[c].begin() + v[c].size() / 2;
                    std::nth_element(v[c].begin(), mid, v[c].end());
                    d[c] = *mid;
                }
            }
    });
}

void crystallize(Image& img, int cell, uint32_t seed) {
    cell = std::max(3, cell);
    Image src = img;
    int gw = img.w / cell + 2, gh = img.h / cell + 2;
    auto site = [&](int gx, int gy, float& sx, float& sy) {
        sx = (gx + hashf(gx, gy, seed)) * cell;
        sy = (gy + hashf(gx, gy, seed + 7)) * cell;
    };
    parallelRows(0, img.h, [&](int y0, int y1) {
        for (int y = y0; y < y1; y++)
            for (int x = 0; x < img.w; x++) {
                int gx = x / cell, gy = y / cell;
                float best = 1e30f, bx = 0, by = 0;
                for (int j = -1; j <= 1; j++)
                    for (int i = -1; i <= 1; i++) {
                        int cx = gx + i, cy = gy + j;
                        if (cx < 0 || cy < 0 || cx >= gw || cy >= gh) continue;
                        float sx, sy;
                        site(cx, cy, sx, sy);
                        float d = (sx - x) * (sx - x) + (sy - y) * (sy - y);
                        if (d < best) { best = d; bx = sx; by = sy; }
                    }
                img.set(x, y, src.get(std::clamp(int(bx), 0, img.w - 1), std::clamp(int(by), 0, img.h - 1)));
            }
    });
}

void sketch(Image& img, float strength) {
    // Pencil sketch: color dodge of the image with its blurred negative.
    Image gray = img;
    desaturate(gray);
    Image inv = gray;
    invert(inv);
    gaussianBlur(inv, 6.f);
    float k = strength / 100.f;
    for (size_t i = 0; i < img.px.size(); i += 4) {
        float b = gray.px[i] / 255.f, s = inv.px[i] / 255.f;
        float v = s >= 1 ? 1 : std::min(1.f, b / (1 - s));
        uint8_t g = clamp8(v * 255);
        img.px[i] = clamp8(img.px[i] + (g - img.px[i]) * k);
        img.px[i + 1] = clamp8(img.px[i + 1] + (g - img.px[i + 1]) * k);
        img.px[i + 2] = clamp8(img.px[i + 2] + (g - img.px[i + 2]) * k);
    }
}

void solarize(Image& img) {
    uint8_t t[256];
    for (int i = 0; i < 256; i++) t[i] = uint8_t(i < 128 ? i : 255 - i);
    lut(img, t);
}

}  // namespace ag
