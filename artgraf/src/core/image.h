#pragma once
#include <algorithm>
#include <cstdint>
#include <vector>

namespace ag {

struct RGBA {
    uint8_t r = 0, g = 0, b = 0, a = 0;
    bool operator==(const RGBA& o) const { return r == o.r && g == o.g && b == o.b && a == o.a; }
};

struct Rect {
    int x0 = 0, y0 = 0, x1 = 0, y1 = 0;  // half-open: [x0, x1) x [y0, y1)

    static Rect of(int x, int y, int w, int h) { return {x, y, x + w, y + h}; }
    int w() const { return x1 - x0; }
    int h() const { return y1 - y0; }
    bool empty() const { return x1 <= x0 || y1 <= y0; }
    Rect unite(const Rect& o) const {
        if (empty()) return o;
        if (o.empty()) return *this;
        return {std::min(x0, o.x0), std::min(y0, o.y0), std::max(x1, o.x1), std::max(y1, o.y1)};
    }
    Rect intersect(const Rect& o) const {
        Rect r{std::max(x0, o.x0), std::max(y0, o.y0), std::min(x1, o.x1), std::min(y1, o.y1)};
        if (r.empty()) return {};
        return r;
    }
    Rect expand(int d) const { return {x0 - d, y0 - d, x1 + d, y1 + d}; }
};

// Straight (non-premultiplied) RGBA8 image.
struct Image {
    int w = 0, h = 0;
    std::vector<uint8_t> px;

    Image() = default;
    Image(int w, int h, RGBA fill = {});

    bool valid() const { return w > 0 && h > 0; }
    Rect bounds() const { return {0, 0, w, h}; }
    uint8_t* at(int x, int y) { return &px[(size_t(y) * w + x) * 4]; }
    const uint8_t* at(int x, int y) const { return &px[(size_t(y) * w + x) * 4]; }
    RGBA get(int x, int y) const {
        const uint8_t* p = at(x, y);
        return {p[0], p[1], p[2], p[3]};
    }
    void set(int x, int y, RGBA c) {
        uint8_t* p = at(x, y);
        p[0] = c.r; p[1] = c.g; p[2] = c.b; p[3] = c.a;
    }

    void fill(RGBA c);
    void clear() { std::fill(px.begin(), px.end(), uint8_t(0)); }
    Image crop(Rect r) const;                       // area outside the image comes out transparent
    void blit(const Image& src, int dx, int dy);    // overwrite
    void drawOver(const Image& src, int dx, int dy, float opacity = 1.f);
    Rect opaqueBounds() const;

    Image resized(int nw, int nh) const;
    Image rotatedCW() const;
    Image rotatedCCW() const;
    void rotate180();
    void flipH();
    void flipV();
};

// Source-over of straight-alpha colors; a is an extra 0..1 multiplier on src alpha.
RGBA over(RGBA dst, RGBA src, float a = 1.f);
RGBA lerp(RGBA a, RGBA b, float t);

inline uint8_t clamp8(float v) { return uint8_t(v < 0 ? 0 : v > 255 ? 255 : v + 0.5f); }
inline uint8_t clamp8i(int v) { return uint8_t(v < 0 ? 0 : v > 255 ? 255 : v); }

}  // namespace ag
