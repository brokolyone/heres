#include "image.h"

#include <cstring>

#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include <stb_image_resize2.h>

namespace ag {

Image::Image(int w_, int h_, RGBA c) : w(w_), h(h_), px(size_t(w_) * h_ * 4) {
    if (c.r || c.g || c.b || c.a) fill(c);
}

void Image::fill(RGBA c) {
    for (size_t i = 0; i < px.size(); i += 4) {
        px[i] = c.r; px[i + 1] = c.g; px[i + 2] = c.b; px[i + 3] = c.a;
    }
}

Image Image::crop(Rect r) const {
    Image out(r.w(), r.h());
    Rect s = r.intersect(bounds());
    for (int y = s.y0; y < s.y1; y++)
        std::memcpy(out.at(s.x0 - r.x0, y - r.y0), at(s.x0, y), size_t(s.w()) * 4);
    return out;
}

void Image::blit(const Image& src, int dx, int dy) {
    Rect d = Rect::of(dx, dy, src.w, src.h).intersect(bounds());
    for (int y = d.y0; y < d.y1; y++)
        std::memcpy(at(d.x0, y), src.at(d.x0 - dx, y - dy), size_t(d.w()) * 4);
}

void Image::drawOver(const Image& src, int dx, int dy, float opacity) {
    Rect d = Rect::of(dx, dy, src.w, src.h).intersect(bounds());
    for (int y = d.y0; y < d.y1; y++)
        for (int x = d.x0; x < d.x1; x++) set(x, y, over(get(x, y), src.get(x - dx, y - dy), opacity));
}

Rect Image::opaqueBounds() const {
    Rect r{w, h, 0, 0};
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++)
            if (at(x, y)[3]) {
                r.x0 = std::min(r.x0, x); r.x1 = std::max(r.x1, x + 1);
                r.y0 = std::min(r.y0, y); r.y1 = std::max(r.y1, y + 1);
            }
    return r.empty() ? Rect{} : r;
}

Image Image::resized(int nw, int nh) const {
    Image out(nw, nh);
    if (!valid() || nw <= 0 || nh <= 0) return out;
    stbir_resize_uint8_linear(px.data(), w, h, 0, out.px.data(), nw, nh, 0, STBIR_RGBA);
    return out;
}

Image Image::rotatedCW() const {
    Image out(h, w);
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) out.set(h - 1 - y, x, get(x, y));
    return out;
}

Image Image::rotatedCCW() const {
    Image out(h, w);
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) out.set(y, w - 1 - x, get(x, y));
    return out;
}

void Image::rotate180() {
    flipH();
    flipV();
}

void Image::flipH() {
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w / 2; x++) {
            RGBA a = get(x, y);
            set(x, y, get(w - 1 - x, y));
            set(w - 1 - x, y, a);
        }
}

void Image::flipV() {
    std::vector<uint8_t> row(size_t(w) * 4);
    for (int y = 0; y < h / 2; y++) {
        std::memcpy(row.data(), at(0, y), row.size());
        std::memcpy(at(0, y), at(0, h - 1 - y), row.size());
        std::memcpy(at(0, h - 1 - y), row.data(), row.size());
    }
}

RGBA over(RGBA d, RGBA s, float a) {
    float sa = s.a / 255.f * a;
    if (sa <= 0.f) return d;
    float da = d.a / 255.f;
    float oa = sa + da * (1.f - sa);
    if (oa <= 0.f) return {};
    float k = da * (1.f - sa);
    return {clamp8((s.r * sa + d.r * k) / oa), clamp8((s.g * sa + d.g * k) / oa),
            clamp8((s.b * sa + d.b * k) / oa), clamp8(oa * 255.f)};
}

RGBA lerp(RGBA a, RGBA b, float t) {
    return {clamp8(a.r + (b.r - a.r) * t), clamp8(a.g + (b.g - a.g) * t), clamp8(a.b + (b.b - a.b) * t),
            clamp8(a.a + (b.a - a.a) * t)};
}

}  // namespace ag
