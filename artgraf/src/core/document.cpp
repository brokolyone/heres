#include "document.h"

#include <cmath>

#include "filters.h"
#include "parallel.h"

namespace ag {

// ---------------------------------------------------------------- Selection

Rect Selection::bounds() const {
    if (mask.empty()) return {0, 0, w, h};
    Rect r{w, h, 0, 0};
    for (int y = 0; y < h; y++) {
        const uint8_t* row = &mask[size_t(y) * w];
        for (int x = 0; x < w; x++)
            if (row[x]) {
                r.x0 = std::min(r.x0, x); r.x1 = std::max(r.x1, x + 1);
                r.y0 = std::min(r.y0, y); r.y1 = std::max(r.y1, y + 1);
            }
    }
    return r.empty() ? Rect{} : r;
}

void Selection::combine(const std::vector<uint8_t>& shape, Op op) {
    size_t n = size_t(w) * h;
    if (mask.empty()) {
        if (op == Op::Subtract) return;  // subtracting from "no selection" keeps nothing selected
        mask = shape;
    } else {
        for (size_t i = 0; i < n; i++) {
            switch (op) {
                case Op::Replace: mask[i] = shape[i]; break;
                case Op::Add: mask[i] = std::max(mask[i], shape[i]); break;
                case Op::Subtract: mask[i] = uint8_t(mask[i] * (255 - shape[i]) / 255); break;
                case Op::Intersect: mask[i] = uint8_t(mask[i] * shape[i] / 255); break;
            }
        }
    }
    // An all-zero mask would block every edit; treat it as "no selection".
    bool any = false;
    for (uint8_t v : mask) if (v) { any = true; break; }
    if (!any) mask.clear();
}

void Selection::selectAll() { mask.assign(size_t(w) * h, 255); }

void Selection::invert() {
    if (mask.empty()) return;  // inverse of "everything" is nothing; keep it simple
    for (auto& v : mask) v = uint8_t(255 - v);
}

void Selection::feather(float radius) {
    if (mask.empty() || radius <= 0) return;
    std::vector<float> f(mask.begin(), mask.end());
    gaussianPlane(f.data(), w, h, radius);
    for (size_t i = 0; i < f.size(); i++) mask[i] = clamp8(f[i]);
}

void Selection::translate(int dx, int dy) {
    if (mask.empty()) return;
    std::vector<uint8_t> out(mask.size(), 0);
    for (int y = 0; y < h; y++) {
        int sy = y - dy;
        if (sy < 0 || sy >= h) continue;
        for (int x = 0; x < w; x++) {
            int sx = x - dx;
            if (sx >= 0 && sx < w) out[size_t(y) * w + x] = mask[size_t(sy) * w + sx];
        }
    }
    mask.swap(out);
}

// ---------------------------------------------------------------- Document

Document Document::blank(int w, int h, RGBA bg) {
    Document d;
    d.w = w; d.h = h;
    d.sel.reset(w, h);
    d.layers.push_back({bg.a ? "Фон" : "Слой 1", Image(w, h, bg)});
    return d;
}

Document Document::fromImage(Image img, const std::string& title) {
    Document d;
    d.w = img.w; d.h = img.h;
    d.sel.reset(d.w, d.h);
    d.title = title;
    d.layers.push_back({"Фон", std::move(img)});
    return d;
}

void Document::composite(Rect r, Image& out, const Image* ov, bool checker) const {
    Rect req = r;
    r = r.intersect({0, 0, w, h});
    if (r.empty()) return;
    parallelRows(r.y0, r.y1, [&](int ya, int yb) { compositeRows(r, req, ya, yb, out, ov, checker); });
}

void Document::compositeRows(Rect r, Rect req, int ya, int yb, Image& out, const Image* ov, bool checker) const {
    for (int y = ya; y < yb; y++) {
        for (int x = r.x0; x < r.x1; x++) {
            RGBA acc{};
            for (size_t i = 0; i < layers.size(); i++) {
                const Layer& L = layers[i];
                if (!L.visible || L.opacity <= 0.f) continue;
                RGBA s = (ov && int(i) == active) ? ov->get(x - req.x0, y - req.y0) : L.img.get(x, y);
                if (s.a) acc = blendPixel(acc, s, L.blend, L.opacity);
            }
            if (checker) {
                uint8_t c = (((x >> 3) + (y >> 3)) & 1) ? 204 : 255;
                acc = over({c, c, c, 255}, acc);
            }
            out.set(x, y, acc);
        }
    }
}

Image Document::flatten() const {
    Image out(w, h);
    composite({0, 0, w, h}, out);
    return out;
}

std::string Document::nextLayerName() const {
    for (int n = int(layers.size()) + 1;; n++) {
        std::string name = "Слой " + std::to_string(n);
        bool used = false;
        for (auto& l : layers) used |= l.name == name;
        if (!used) return name;
    }
}

void Document::addLayer(const std::string& name, Image img) {
    if (!img.valid()) img = Image(w, h);
    layers.insert(layers.begin() + active + 1, Layer{name, std::move(img)});
    active++;
}

void Document::duplicateLayer() {
    Layer copy = layers[active];
    copy.name += " копия";
    layers.insert(layers.begin() + active + 1, std::move(copy));
    active++;
}

void Document::deleteLayer() {
    if (layers.size() <= 1) return;
    layers.erase(layers.begin() + active);
    active = std::min(active, int(layers.size()) - 1);
}

void Document::moveLayer(int delta) {
    int to = active + delta;
    if (to < 0 || to >= int(layers.size())) return;
    std::swap(layers[active], layers[to]);
    active = to;
}

void Document::mergeDown() {
    if (active == 0) return;
    Layer& top = layers[active];
    Layer& bottom = layers[active - 1];
    if (top.visible) {
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++) {
                RGBA s = top.img.get(x, y);
                if (s.a) bottom.img.set(x, y, blendPixel(bottom.img.get(x, y), s, top.blend, top.opacity));
            }
    }
    layers.erase(layers.begin() + active);
    active--;
}

void Document::flattenAll() {
    Image flat = flatten();
    Image bg(w, h, {255, 255, 255, 255});
    bg.drawOver(flat, 0, 0);
    layers.clear();
    layers.push_back({"Фон", std::move(bg)});
    active = 0;
}

void Document::resizeImage(int nw, int nh) {
    for (auto& l : layers) l.img = l.img.resized(nw, nh);
    w = nw; h = nh;
    sel.reset(w, h);
}

void Document::resizeCanvas(int nw, int nh, int offX, int offY) {
    for (auto& l : layers) {
        Image n(nw, nh);
        n.blit(l.img, offX, offY);
        l.img = std::move(n);
    }
    w = nw; h = nh;
    sel.reset(w, h);
}

void Document::crop(Rect r) {
    r = r.intersect({0, 0, w, h});
    if (r.empty()) return;
    for (auto& l : layers) l.img = l.img.crop(r);
    w = r.w(); h = r.h();
    sel.reset(w, h);
}

void Document::rotateCW() {
    for (auto& l : layers) l.img = l.img.rotatedCW();
    std::swap(w, h);
    sel.reset(w, h);
}

void Document::rotateCCW() {
    for (auto& l : layers) l.img = l.img.rotatedCCW();
    std::swap(w, h);
    sel.reset(w, h);
}

void Document::rotate180() {
    for (auto& l : layers) l.img.rotate180();
    sel.clear();
}

void Document::flipH() {
    for (auto& l : layers) l.img.flipH();
    sel.clear();
}

void Document::flipV() {
    for (auto& l : layers) l.img.flipV();
    sel.clear();
}

// ---------------------------------------------------------------- History

Document::State Document::capture(const std::string& name) const { return {name, w, h, active, layers}; }

void Document::restore(State& s) {
    bool resized = s.w != w || s.h != h;
    w = s.w; h = s.h; active = s.active;
    layers = std::move(s.layers);
    if (resized) sel.reset(w, h);
    dirty = true;
}

void Document::push(const std::string& name) {
    undoStack.push_back(capture(name));
    if (undoStack.size() > historyLimit) undoStack.erase(undoStack.begin());
    redoStack.clear();
    dirty = true;
}

void Document::popLast() {
    if (!undoStack.empty()) undoStack.pop_back();
}

bool Document::undo() {
    if (undoStack.empty()) return false;
    State s = std::move(undoStack.back());
    undoStack.pop_back();
    redoStack.push_back(capture(s.name));
    restore(s);
    return true;
}

bool Document::redo() {
    if (redoStack.empty()) return false;
    State s = std::move(redoStack.back());
    redoStack.pop_back();
    undoStack.push_back(capture(s.name));
    restore(s);
    return true;
}

}  // namespace ag
