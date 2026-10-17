#include "raster.h"

#include <algorithm>

namespace ag {

namespace {
float sat(float v) { return v < 0 ? 0 : v > 1 ? 1 : v; }
}

void Coverage::reset(int w_, int h_) {
    w = w_; h = h_;
    v.assign(size_t(w) * h, 0);
    touched = {};
}

void Coverage::clear() {
    if (touched.empty()) return;
    for (int y = touched.y0; y < touched.y1; y++) std::fill_n(&v[size_t(y) * w + touched.x0], touched.w(), 0);
    touched = {};
}

void Coverage::put(int x, int y, float c) {
    uint8_t n = clamp8(c * 255.f);
    uint8_t& d = v[size_t(y) * w + x];
    if (n > d) d = n;
}

void Coverage::dab(float cx, float cy, float r, float hard, bool aa) {
    r = std::max(r, 0.5f);
    Rect b = Rect{int(std::floor(cx - r - 1)), int(std::floor(cy - r - 1)), int(std::ceil(cx + r + 1)),
                  int(std::ceil(cy + r + 1))}
                 .intersect({0, 0, w, h});
    if (b.empty()) return;
    touched = touched.unite(b);
    hard = sat(hard);
    float inner = r * hard;
    for (int y = b.y0; y < b.y1; y++)
        for (int x = b.x0; x < b.x1; x++) {
            float dx = x + 0.5f - cx, dy = y + 0.5f - cy;
            float d = std::sqrt(dx * dx + dy * dy);
            float c;
            if (!aa) c = d <= r ? 1.f : 0.f;
            else if (hard >= 0.99f) c = sat(r - d + 0.5f);
            else if (d <= inner) c = 1.f;
            else {
                float t = sat((d - inner) / (r - inner));
                c = 1.f - t * t * (3.f - 2.f * t);
            }
            if (c > 0) put(x, y, c);
        }
}

void Coverage::ellipse(float x0, float y0, float x1, float y1, bool filled, float sw) {
    if (x1 < x0) std::swap(x0, x1);
    if (y1 < y0) std::swap(y0, y1);
    float cx = (x0 + x1) * 0.5f, cy = (y0 + y1) * 0.5f;
    float rx = (x1 - x0) * 0.5f, ry = (y1 - y0) * 0.5f;
    if (!filled) { rx -= sw * 0.5f; ry -= sw * 0.5f; }
    if (rx < 0.5f || ry < 0.5f) return;
    Rect b = Rect{int(std::floor(x0)) - 1, int(std::floor(y0)) - 1, int(std::ceil(x1)) + 1, int(std::ceil(y1)) + 1}
                 .intersect({0, 0, w, h});
    if (b.empty()) return;
    touched = touched.unite(b);
    float mr = std::min(rx, ry);
    for (int y = b.y0; y < b.y1; y++)
        for (int x = b.x0; x < b.x1; x++) {
            float dx = (x + 0.5f - cx) / rx, dy = (y + 0.5f - cy) / ry;
            float d = (std::sqrt(dx * dx + dy * dy) - 1.f) * mr;
            float c = filled ? sat(0.5f - d) : sat(sw * 0.5f + 0.5f - std::fabs(d));
            if (c > 0) put(x, y, c);
        }
}

void Coverage::rect(float x0, float y0, float x1, float y1, bool filled, float sw) {
    if (x1 < x0) std::swap(x0, x1);
    if (y1 < y0) std::swap(y0, y1);
    Rect b = Rect{int(std::floor(x0)), int(std::floor(y0)), int(std::ceil(x1)), int(std::ceil(y1))}.intersect({0, 0, w, h});
    if (b.empty()) return;
    touched = touched.unite(b);
    auto cov = [](float px, float py, float ax, float ay, float bx, float by) {
        if (bx <= ax || by <= ay) return 0.f;
        return sat(std::min(px + 1, bx) - std::max(px, ax)) * sat(std::min(py + 1, by) - std::max(py, ay));
    };
    for (int y = b.y0; y < b.y1; y++)
        for (int x = b.x0; x < b.x1; x++) {
            float c = cov(float(x), float(y), x0, y0, x1, y1);
            if (!filled) c -= cov(float(x), float(y), x0 + sw, y0 + sw, x1 - sw, y1 - sw);
            if (c > 0) put(x, y, c);
        }
}

void Coverage::line(float x0, float y0, float x1, float y1, float width) {
    float r = width * 0.5f;
    Rect b = Rect{int(std::floor(std::min(x0, x1) - r - 1)), int(std::floor(std::min(y0, y1) - r - 1)),
                  int(std::ceil(std::max(x0, x1) + r + 1)), int(std::ceil(std::max(y0, y1) + r + 1))}
                 .intersect({0, 0, w, h});
    if (b.empty()) return;
    touched = touched.unite(b);
    float vx = x1 - x0, vy = y1 - y0;
    float len2 = vx * vx + vy * vy;
    for (int y = b.y0; y < b.y1; y++)
        for (int x = b.x0; x < b.x1; x++) {
            float px = x + 0.5f - x0, py = y + 0.5f - y0;
            float t = len2 > 0 ? sat((px * vx + py * vy) / len2) : 0.f;
            float dx = px - vx * t, dy = py - vy * t;
            float c = sat(r + 0.5f - std::sqrt(dx * dx + dy * dy));
            if (c > 0) put(x, y, c);
        }
}

void Coverage::polygon(const std::vector<Vec2>& pts) {
    if (pts.size() < 3) return;
    float minY = pts[0].y, maxY = pts[0].y;
    for (auto& p : pts) { minY = std::min(minY, p.y); maxY = std::max(maxY, p.y); }
    int y0 = std::max(0, int(std::floor(minY))), y1 = std::min(h, int(std::ceil(maxY)) + 1);
    std::vector<float> xs;
    for (int y = y0; y < y1; y++) {
        float sy = y + 0.5f;
        xs.clear();
        for (size_t i = 0, n = pts.size(); i < n; i++) {
            Vec2 a = pts[i], b = pts[(i + 1) % n];
            if ((a.y <= sy && b.y > sy) || (b.y <= sy && a.y > sy)) xs.push_back(a.x + (sy - a.y) / (b.y - a.y) * (b.x - a.x));
        }
        std::sort(xs.begin(), xs.end());
        for (size_t i = 0; i + 1 < xs.size(); i += 2) {
            int xa = std::max(0, int(std::ceil(xs[i] - 0.5f))), xb = std::min(w, int(std::ceil(xs[i + 1] - 0.5f)));
            if (xb <= xa) continue;
            std::fill_n(&v[size_t(y) * w + xa], xb - xa, 255);
            touched = touched.unite({xa, y, xb, y + 1});
        }
    }
}

void Coverage::fillAll() {
    std::fill(v.begin(), v.end(), 255);
    touched = {0, 0, w, h};
}

std::vector<uint8_t> floodMask(const Image& img, int sx, int sy, int tol, bool contiguous) {
    int w = img.w, h = img.h;
    std::vector<uint8_t> out(size_t(w) * h, 0);
    if (sx < 0 || sy < 0 || sx >= w || sy >= h) return out;
    const uint8_t* t = img.at(sx, sy);
    int tr = t[0], tg = t[1], tb = t[2], ta = t[3];
    auto match = [&](size_t p) {
        const uint8_t* q = &img.px[p * 4];
        // Fully transparent pixels all count as the same color.
        if (ta == 0 && q[3] == 0) return true;
        return std::abs(q[0] - tr) <= tol && std::abs(q[1] - tg) <= tol && std::abs(q[2] - tb) <= tol &&
               std::abs(q[3] - ta) <= tol;
    };
    if (!contiguous) {
        for (size_t p = 0, n = size_t(w) * h; p < n; p++) if (match(p)) out[p] = 255;
        return out;
    }
    std::vector<size_t> stack{size_t(sy) * w + sx};
    while (!stack.empty()) {
        size_t p = stack.back();
        stack.pop_back();
        if (out[p] || !match(p)) continue;
        int y = int(p / w), x = int(p % w);
        size_t row = size_t(y) * w;
        int lx = x, rx = x;
        while (lx > 0 && !out[row + lx - 1] && match(row + lx - 1)) lx--;
        while (rx < w - 1 && !out[row + rx + 1] && match(row + rx + 1)) rx++;
        bool upOpen = false, downOpen = false;
        for (int i = lx; i <= rx; i++) {
            size_t q = row + i;
            out[q] = 255;
            // Push one seed per run of matching pixels in the neighbouring rows.
            if (y > 0) {
                bool m = !out[q - w] && match(q - w);
                if (m && !upOpen) stack.push_back(q - w);
                upOpen = m;
            }
            if (y < h - 1) {
                bool m = !out[q + w] && match(q + w);
                if (m && !downOpen) stack.push_back(q + w);
                downOpen = m;
            }
        }
    }
    return out;
}

}  // namespace ag
