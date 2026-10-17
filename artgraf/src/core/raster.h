#pragma once
#include <cmath>
#include <cstdint>
#include <vector>

#include "image.h"

namespace ag {

struct Vec2 { float x = 0, y = 0; };

// 8-bit coverage plane the size of the document. Brush dabs, shapes and text are rendered
// here first and then composited into a layer, so a single stroke never darkens itself.
struct Coverage {
    int w = 0, h = 0;
    std::vector<uint8_t> v;
    Rect touched;  // union of everything drawn since reset()

    void reset(int w_, int h_);
    void clear();
    uint8_t at(int x, int y) const { return v[size_t(y) * w + x]; }
    void put(int x, int y, float c);  // max-combine
    void add(int x, int y, float c);  // accumulate (airbrush)

    // hardness 0..1; aa=false gives hard pixel edges (pencil)
    void dab(float cx, float cy, float radius, float hardness, bool aa);
    void ellipse(float x0, float y0, float x1, float y1, bool filled, float strokeW);
    void rect(float x0, float y0, float x1, float y1, bool filled, float strokeW);
    void line(float x0, float y0, float x1, float y1, float width);
    void polygon(const std::vector<Vec2>& pts);  // even-odd, no antialiasing
    void polygonAA(const std::vector<Vec2>& pts);  // even-odd, antialiased
    void polyline(const std::vector<Vec2>& pts, float width, bool closed);
    void fillAll();
};

// Places dabs along a path with even spacing, carrying the remainder between segments.
struct Stroker {
    Vec2 last;
    float carry = 0;
    bool started = false;

    template <class F>
    void begin(Vec2 p, F&& dab) {
        last = p;
        carry = 0;
        started = true;
        dab(p);
    }
    template <class F>
    void to(Vec2 p, float spacing, F&& dab) {
        float dx = p.x - last.x, dy = p.y - last.y;
        float len = std::sqrt(dx * dx + dy * dy);
        if (len <= 0.f) return;
        float t = spacing - carry;
        while (t <= len) {
            dab(Vec2{last.x + dx * t / len, last.y + dy * t / len});
            t += spacing;
        }
        carry = len - (t - spacing);
        last = p;
    }
};

// Pixels similar to the one at (x, y): within `tolerance` on every channel. 255 = in region.
std::vector<uint8_t> floodMask(const Image& img, int x, int y, int tolerance, bool contiguous);

}  // namespace ag
