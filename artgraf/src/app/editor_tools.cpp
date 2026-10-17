#include <cmath>

#include "editor.h"
#include "parallel.h"

namespace ag {

namespace {

constexpr float kPi = 3.14159265f;

Vec2 constrain45(Vec2 a, Vec2 b) {
    float dx = b.x - a.x, dy = b.y - a.y;
    float ang = std::round(std::atan2(dy, dx) / (kPi / 4)) * (kPi / 4);
    float len = std::sqrt(dx * dx + dy * dy);
    return {a.x + std::cos(ang) * len, a.y + std::sin(ang) * len};
}

Vec2 constrainSquare(Vec2 a, Vec2 b) {
    float dx = b.x - a.x, dy = b.y - a.y;
    float m = std::max(std::fabs(dx), std::fabs(dy));
    return {a.x + (dx < 0 ? -m : m), a.y + (dy < 0 ? -m : m)};
}

Rect rectFrom(Vec2 a, Vec2 b) {
    return {int(std::floor(std::min(a.x, b.x))), int(std::floor(std::min(a.y, b.y))), int(std::ceil(std::max(a.x, b.x))),
            int(std::ceil(std::max(a.y, b.y)))};
}

std::string utf8Prefix(const std::string& s, size_t n) {
    if (s.size() <= n) return s;
    while (n > 0 && (uint8_t(s[n]) & 0xC0) == 0x80) n--;
    return s.substr(0, n) + "…";
}

uint32_t hash2(int x, int y) {
    uint32_t h = uint32_t(x) * 374761393u + uint32_t(y) * 668265263u;
    h = (h ^ (h >> 13)) * 1274126177u;
    return h ^ (h >> 16);
}

// Outline points for the shape kinds that are polygons.
std::vector<Vec2> shapePoints(ShapeKind k, Vec2 a, Vec2 b, float radius, int sides) {
    float x0 = std::min(a.x, b.x), x1 = std::max(a.x, b.x), y0 = std::min(a.y, b.y), y1 = std::max(a.y, b.y);
    float cx = (x0 + x1) * 0.5f, cy = (y0 + y1) * 0.5f, rx = (x1 - x0) * 0.5f, ry = (y1 - y0) * 0.5f;
    std::vector<Vec2> p;
    switch (k) {
        case ShapeKind::RoundRect: {
            float r = std::min({radius, rx, ry});
            const Vec2 corners[4] = {{x1 - r, y0 + r}, {x1 - r, y1 - r}, {x0 + r, y1 - r}, {x0 + r, y0 + r}};
            for (int c = 0; c < 4; c++)
                for (int i = 0; i <= 8; i++) {
                    float t = (c * 90.f - 90.f + i * 90.f / 8) * kPi / 180.f;
                    p.push_back({corners[c].x + std::cos(t) * r, corners[c].y + std::sin(t) * r});
                }
            break;
        }
        case ShapeKind::Polygon:
            for (int i = 0; i < sides; i++) {
                float t = -kPi / 2 + i * 2 * kPi / sides;
                p.push_back({cx + std::cos(t) * rx, cy + std::sin(t) * ry});
            }
            break;
        case ShapeKind::Star:
            for (int i = 0; i < sides * 2; i++) {
                float t = -kPi / 2 + i * kPi / sides, k2 = i % 2 ? 0.45f : 1.f;
                p.push_back({cx + std::cos(t) * rx * k2, cy + std::sin(t) * ry * k2});
            }
            break;
        case ShapeKind::Heart:
            for (int i = 0; i < 72; i++) {
                float t = i * 2 * kPi / 72;
                float hx = 16 * std::pow(std::sin(t), 3.f);
                float hy = -(13 * std::cos(t) - 5 * std::cos(2 * t) - 2 * std::cos(3 * t) - std::cos(4 * t));
                p.push_back({cx + hx / 17.f * rx, cy + (hy + 2.5f) / 15.5f * ry});
            }
            break;
        default: break;
    }
    return p;
}

}  // namespace

void Editor::setTool(Tool t) {
    for (size_t g = 0; g < toolGroups().size(); g++)
        for (Tool x : toolGroups()[g])
            if (x == t) groupTool[int(g)] = t;
    if (t == tool) return;
    if (textEditing) commitText();
    if (dragging) {
        dragging = false;
        cancelLive();
    }
    polyActive = false;
    lasso.clear();
    cropActive = false;
    tool = t;
}

Selection::Op Editor::selOpFromMods() const {
    if (downShift && downAlt) return Selection::Op::Intersect;
    if (downShift) return Selection::Op::Add;
    if (downAlt) return Selection::Op::Subtract;
    return Selection::Op(selMode);
}

void Editor::combineSelection(std::vector<uint8_t> shape, Selection::Op op) {
    if (selFeather > 0) {
        Selection tmp;
        tmp.reset(doc->w, doc->h);
        tmp.mask = std::move(shape);
        tmp.feather(selFeather);
        shape = std::move(tmp.mask);
    }
    doc->sel.combine(shape, op);
    selectionChanged();
}

RGBA Editor::gradientAt(int x, int y) const {
    float t = gradientT(gradType, gradA.x, gradA.y, gradB.x, gradB.y, x + 0.5f, y + 0.5f);
    if (gradDither) t += ((hash2(x, y) & 1023) / 1023.f - 0.5f) / 255.f;  // breaks up banding
    RGBA c = liveGrad.sample(t);
    c.a = clamp8(c.a * gradOpacity);
    return c;
}

const BrushTip& Editor::tipOf(const BrushPreset& p) {
    static BrushTip none;
    if (p.shape == TipShape::Custom)
        return p.customId >= 0 && p.customId < int(customTips.size()) ? customTips[size_t(p.customId)] : none;
    return tipFor(p.shape, p.hardness);
}

float Editor::spacingPx() const {
    const BrushPreset& p = tb.at(tool).preset;
    return std::max(0.5f, p.size * p.spacing);
}

// ---------------------------------------------------------------- live operations

void Editor::beginStroke(Source src, RGBA color, float opacity) {
    cancelLive();
    live = Live::Stroke;
    source = src;
    liveColor = color;
    liveOpacity = opacity;
    if (cov.w != doc->w || cov.h != doc->h) cov.reset(doc->w, doc->h);
    else cov.clear();
}

RGBA Editor::livePixel(RGBA dst, int x, int y) const {
    uint8_t c = cov.at(x, y);
    if (!c) return dst;
    float a = c / 255.f * liveOpacity * (doc->sel.at(x, y) / 255.f);
    if (a <= 0.f) return dst;
    switch (source) {
        case Source::Solid: return over(dst, liveColor, a);
        case Source::Erase: dst.a = clamp8(dst.a * (1.f - a)); return dst;
        case Source::Clone: {
            int sx = x + cloneDx, sy = y + cloneDy;
            if (sx < 0 || sy < 0 || sx >= cloneSnap.w || sy >= cloneSnap.h) return dst;
            return over(dst, cloneSnap.get(sx, sy), a);
        }
        case Source::Gradient: return over(dst, gradientAt(x, y), a);
    }
    return dst;
}

bool Editor::previewActive(Rect r, Image& out) const {
    if (live == Live::None || !doc) return false;
    const Image& L = doc->layer().img;
    Rect c = r.intersect({0, 0, doc->w, doc->h});
    parallelRows(c.y0, c.y1, [&](int y0, int y1) {
        for (int y = y0; y < y1; y++)
            for (int x = c.x0; x < c.x1; x++) {
                RGBA v;
                if (live == Live::Stroke) {
                    v = livePixel(L.get(x, y), x, y);
                } else {
                    v = moveBase.get(x, y);
                    int fx = x - moveDx, fy = y - moveDy;
                    if (fx >= 0 && fy >= 0 && fx < moveFloat.w && fy < moveFloat.h) v = over(v, moveFloat.get(fx, fy));
                }
                out.set(x - r.x0, y - r.y0, v);
            }
    });
    return true;
}

void Editor::cancelLive() {
    if (!doc) {
        live = Live::None;
        return;
    }
    if (live == Live::Move) invalidateAll();
    if (!cov.touched.empty()) invalidate(cov.touched);
    if (cov.w) cov.clear();
    live = Live::None;
    moveBase = {};
    moveFloat = {};
}

void Editor::commitStroke(const char* name, bool toNewLayer, const std::string& layerName) {
    if (live != Live::Stroke || !doc) return;
    Rect t = cov.touched;
    if (t.empty()) {
        live = Live::None;
        return;
    }
    doc->push(name);
    if (toNewLayer) doc->addLayer(layerName.empty() ? doc->nextLayerName() : layerName);
    Image& L = doc->layer().img;
    parallelRows(t.y0, t.y1, [&](int y0, int y1) {
        for (int y = y0; y < y1; y++)
            for (int x = t.x0; x < t.x1; x++) L.set(x, y, livePixel(L.get(x, y), x, y));
    });
    live = Live::None;
    cov.clear();
    invalidate(t);
    thumbsDirty = true;
}

void Editor::brushDab(Vec2 p) {
    const BrushPreset& pr = brush().preset;
    Rect r = stamper.dab(cov, pr, tipOf(pr), p.x, p.y, strokeDir);
    invalidate(r.expand(1));
}

void Editor::retouchDab(Vec2 p) {
    const ToolBrush& b = brush();
    RetouchParams rp;
    rp.radius = b.preset.size * 0.5f;
    rp.hardness = b.preset.hardness;
    rp.strength = b.strength;
    rp.range = dodgeRange;
    rp.saturate = spongeSaturate;
    switch (tool) {
        case Tool::Blur: rp.mode = RetouchMode::Blur; break;
        case Tool::Sharpen: rp.mode = RetouchMode::Sharpen; break;
        case Tool::Smudge: rp.mode = RetouchMode::Smudge; break;
        case Tool::Dodge: rp.mode = RetouchMode::Dodge; break;
        case Tool::Burn: rp.mode = RetouchMode::Burn; break;
        default: rp.mode = RetouchMode::Sponge; break;
    }
    Rect r = retoucher.dab(doc->layer().img, p.x, p.y, rp, doc->sel.mask);
    invalidate(r);
}

void Editor::nudge(int dx, int dy) {
    if (!doc || live != Live::None) return;
    toolDown({0, 0});
    moveDx = dx;
    moveDy = dy;
    toolUp({0, 0});
}

void Editor::drawShapeCoverage(Vec2 a, Vec2 b) {
    switch (shapeKind) {
        case ShapeKind::Rect: cov.rect(a.x, a.y, b.x, b.y, shapeFilled, shapeStroke); break;
        case ShapeKind::Ellipse: cov.ellipse(a.x, a.y, b.x, b.y, shapeFilled, shapeStroke); break;
        case ShapeKind::Line: cov.line(a.x, a.y, b.x, b.y, shapeStroke); break;
        case ShapeKind::Arrow: {
            float dx = b.x - a.x, dy = b.y - a.y, len = std::hypot(dx, dy);
            if (len < 1) break;
            float ux = dx / len, uy = dy / len, head = std::max(shapeStroke * 4.f, 12.f);
            Vec2 base{b.x - ux * head, b.y - uy * head};
            cov.line(a.x, a.y, base.x, base.y, shapeStroke);
            cov.polygonAA({{b.x, b.y}, {base.x - uy * head * 0.6f, base.y + ux * head * 0.6f}, {base.x + uy * head * 0.6f, base.y - ux * head * 0.6f}});
            break;
        }
        default: {
            auto pts = shapePoints(shapeKind, a, b, shapeRadius, std::max(3, shapeSides));
            if (shapeFilled) cov.polygonAA(pts);
            else cov.polyline(pts, shapeStroke, true);
        }
    }
}

// ---------------------------------------------------------------- pointer handling

void Editor::canvasInput(bool hovered, bool) {
    ImGuiIO& io = ImGui::GetIO();
    ImVec2 m = io.MousePos;
    curPt = toDoc(m);

    if (hovered && io.MouseWheel != 0.f) zoomAt(zoom * std::pow(1.2f, io.MouseWheel), m);
    if (hovered && io.MouseWheelH != 0.f) pan.x += io.MouseWheelH * 40.f;

    bool space = ImGui::IsKeyDown(ImGuiKey_Space) && !io.WantTextInput;
    bool panClick = ImGui::IsMouseClicked(ImGuiMouseButton_Middle) ||
                    (ImGui::IsMouseClicked(ImGuiMouseButton_Left) && (space || tool == Tool::Hand));
    if (hovered && panClick && !dragging) {
        panning = true;
        panStartMouse = m;
        panStartPan = pan;
    }
    if (panning) {
        pan = ImVec2(panStartPan.x + m.x - panStartMouse.x, panStartPan.y + m.y - panStartMouse.y);
        if (!ImGui::IsMouseDown(ImGuiMouseButton_Left) && !ImGui::IsMouseDown(ImGuiMouseButton_Middle)) panning = false;
        ImGui::SetMouseCursor(ImGuiMouseCursor_Hand);
        return;
    }
    if (!doc) return;

    if (touchFingers >= 2) return;  // two-finger gesture in progress: no tool input
    if (hovered && ImGui::IsMouseClicked(ImGuiMouseButton_Left)) {
        downShift = io.KeyShift;
        downAlt = io.KeyAlt;
        downCtrl = io.KeyCtrl;
        dragging = true;
        downPt = lastPt = curPt;
        toolDown(curPt);
        if (tool == Tool::PolyLasso && polyActive && ImGui::IsMouseDoubleClicked(ImGuiMouseButton_Left)) finishPolyLasso();
    } else if (dragging && ImGui::IsMouseDown(ImGuiMouseButton_Left)) {
        if (curPt.x != lastPt.x || curPt.y != lastPt.y) {
            toolDrag(curPt);
            lastPt = curPt;
        }
    } else if (dragging) {
        dragging = false;
        toolUp(curPt);
    }

    if (hovered || dragging) {
        switch (tool) {
            case Tool::Move: ImGui::SetMouseCursor(ImGuiMouseCursor_ResizeAll); break;
            case Tool::Hand: ImGui::SetMouseCursor(ImGuiMouseCursor_Hand); break;
            case Tool::Text: ImGui::SetMouseCursor(ImGuiMouseCursor_TextInput); break;
            case Tool::Zoom: ImGui::SetMouseCursor(ImGuiMouseCursor_Arrow); break;
            default: ImGui::SetMouseCursor(ImGuiMouseCursor_None); break;
        }
    }
}

void Editor::toolDown(Vec2 p) {
    int px = int(std::floor(p.x)), py = int(std::floor(p.y));
    bool inside = px >= 0 && py >= 0 && px < doc->w && py < doc->h;
    smoothPt = p;
    switch (tool) {
        case Tool::Move: {
            cancelLive();
            const Image& L = doc->layer().img;
            moveFloat = L;
            if (doc->sel.active()) {
                moveBase = L;
                for (int y = 0; y < L.h; y++)
                    for (int x = 0; x < L.w; x++) {
                        uint8_t s = doc->sel.at(x, y);
                        moveFloat.at(x, y)[3] = uint8_t(L.at(x, y)[3] * s / 255);
                        moveBase.at(x, y)[3] = uint8_t(L.at(x, y)[3] * (255 - s) / 255);
                    }
                moveBounds = doc->sel.bounds();
            } else {
                moveBase = Image(L.w, L.h);
                moveBounds = L.opaqueBounds();
            }
            moveDx = moveDy = 0;
            live = Live::Move;
            break;
        }
        case Tool::Lasso: lasso = {p}; break;
        case Tool::PolyLasso:
            if (!polyActive) {
                polyActive = true;
                lasso = {p};
            } else {
                Vec2 f = lasso.front();
                if (lasso.size() > 2 && std::hypot(p.x - f.x, p.y - f.y) * zoom < 8) {
                    finishPolyLasso();
                } else {
                    lasso.push_back(p);
                }
            }
            dragging = false;
            break;
        case Tool::MagicWand: {
            if (!inside) break;
            Image merged;
            const Image& src = sampleMerged ? (merged = doc->flatten()) : doc->layer().img;
            combineSelection(floodMask(src, px, py, tolerance, contiguous), selOpFromMods());
            break;
        }
        case Tool::Crop:
            if (cropActive && p.x >= cropRect.x0 && p.y >= cropRect.y0 && p.x < cropRect.x1 && p.y < cropRect.y1) {
                cropMoving = true;
                cropGrab = {p.x - cropRect.x0, p.y - cropRect.y0};
            } else {
                cropMoving = false;
                cropActive = true;
                cropRect = {};
            }
            break;
        case Tool::Eyedropper:
            if (inside) {
                RGBA c = mergedPixel(px, py);
                if (c.a) (downAlt ? secondary : primary) = RGBA{c.r, c.g, c.b, 255};
            }
            break;
        case Tool::Brush:
        case Tool::Pencil:
        case Tool::Eraser: {
            if (downAlt && tool != Tool::Eraser) {
                if (inside) {
                    RGBA c = mergedPixel(px, py);
                    if (c.a) primary = {c.r, c.g, c.b, 255};
                }
                dragging = false;
                break;
            }
            Vec2 from = stroker.last;
            bool line = downShift && stroker.started;
            beginStroke(tool == Tool::Eraser ? Source::Erase : Source::Solid, primary, brush().opacity);
            if (tool != Tool::Eraser) pushRecentColor(primary);
            stamper.reset(uint32_t(SDL_GetTicks()));
            if (line) {
                strokeDir = std::atan2(p.y - from.y, p.x - from.x) * 180.f / kPi;
                stroker.begin(from, [this](Vec2 q) { brushDab(q); });
                stroker.to(p, spacingPx(), [this](Vec2 q) { brushDab(q); });
            } else {
                stroker.begin(p, [this](Vec2 q) { brushDab(q); });
            }
            break;
        }
        case Tool::SpotHeal:
            beginStroke(Source::Solid, {255, 70, 120, 255}, 0.45f);
            stamper.reset(1);
            stroker.begin(p, [this](Vec2 q) { brushDab(q); });
            break;
        case Tool::Clone:
            if (downAlt) {
                cloneSource = p;
                cloneHasSource = true;
                cloneAligned = false;
                status = "Источник задан";
                dragging = false;
                break;
            }
            if (!cloneHasSource) {
                status = "Сначала Alt+клик — выберите точку-источник";
                dragging = false;
                break;
            }
            if (!cloneAligned) {
                cloneDx = int(std::lround(cloneSource.x - p.x));
                cloneDy = int(std::lround(cloneSource.y - p.y));
                cloneAligned = true;
            }
            cloneSnap = sampleMerged ? doc->flatten() : doc->layer().img;
            beginStroke(Source::Clone, {}, brush().opacity);
            stamper.reset(2);
            stroker.begin(p, [this](Vec2 q) { brushDab(q); });
            break;
        case Tool::Blur:
        case Tool::Sharpen:
        case Tool::Smudge:
        case Tool::Dodge:
        case Tool::Burn:
        case Tool::Sponge: {
            cancelLive();
            doc->push(toolInfo(tool).name);
            retouching = true;
            RetouchParams rp;
            rp.mode = tool == Tool::Smudge ? RetouchMode::Smudge : RetouchMode::Blur;
            rp.radius = brush().preset.size * 0.5f;
            retoucher.begin(doc->layer().img, p.x, p.y, rp);
            stroker.begin(p, [this](Vec2 q) { retouchDab(q); });
            break;
        }
        case Tool::Gradient: {
            gradA = gradB = p;
            liveGrad = gradPreset >= 0 ? gradientPresets(primary, secondary)[size_t(gradPreset)] : gradient;
            if (gradReverse) liveGrad = liveGrad.reversed();
            beginStroke(Source::Gradient, {}, 1.f);
            cov.fillAll();
            invalidateAll();
            break;
        }
        case Tool::Bucket: {
            if (!inside) break;
            Image merged;
            const Image& src = sampleMerged ? (merged = doc->flatten()) : doc->layer().img;
            auto mask = floodMask(src, px, py, tolerance, contiguous);
            beginStroke(Source::Solid, primary, brush().opacity);
            cov.v = std::move(mask);
            cov.touched = {0, 0, doc->w, doc->h};
            commitStroke("Заливка");
            pushRecentColor(primary);
            dragging = false;
            break;
        }
        case Tool::Text:
            if (textEditing) {
                commitText();
            } else {
                textEditing = true;
                textPos = p;
                textBuf.clear();
                textFocus = true;
                beginStroke(Source::Solid, primary, 1.f);
            }
            dragging = false;
            break;
        case Tool::Shape: beginStroke(Source::Solid, primary, 1.f); break;
        case Tool::Zoom:
            zoomAt(zoom * (downAlt ? 1 / 1.5f : 1.5f), ImGui::GetIO().MousePos);
            dragging = false;
            break;
        default: break;
    }
}

void Editor::toolDrag(Vec2 p) {
    bool shiftNow = ImGui::GetIO().KeyShift;
    // Stroke stabilizer: the brush trails the cursor.
    if (isBrushTool(tool) && smoothing > 0.01f) {
        float k = 1.f - smoothing;
        smoothPt = {smoothPt.x + (p.x - smoothPt.x) * k, smoothPt.y + (p.y - smoothPt.y) * k};
        p = smoothPt;
    }
    switch (tool) {
        case Tool::Move: {
            if (live != Live::Move) break;
            invalidate(Rect{moveBounds.x0 + moveDx, moveBounds.y0 + moveDy, moveBounds.x1 + moveDx, moveBounds.y1 + moveDy});
            moveDx = int(std::lround(p.x - downPt.x));
            moveDy = int(std::lround(p.y - downPt.y));
            if (shiftNow) {
                if (std::abs(moveDx) > std::abs(moveDy)) moveDy = 0;
                else moveDx = 0;
            }
            invalidate(Rect{moveBounds.x0 + moveDx, moveBounds.y0 + moveDy, moveBounds.x1 + moveDx, moveBounds.y1 + moveDy});
            break;
        }
        case Tool::Lasso: {
            Vec2 l = lasso.back();
            if (std::hypot(p.x - l.x, p.y - l.y) * zoom >= 2.f) lasso.push_back(p);
            break;
        }
        case Tool::Crop:
            if (cropMoving) {
                int w = cropRect.w(), h = cropRect.h();
                int x = std::clamp(int(p.x - cropGrab.x), 0, doc->w - w), y = std::clamp(int(p.y - cropGrab.y), 0, doc->h - h);
                cropRect = Rect::of(x, y, w, h);
            } else {
                Vec2 b = shiftNow ? constrainSquare(downPt, p) : p;
                cropRect = rectFrom(downPt, b).intersect({0, 0, doc->w, doc->h});
            }
            break;
        case Tool::Eyedropper: {
            int px = int(std::floor(p.x)), py = int(std::floor(p.y));
            if (px >= 0 && py >= 0 && px < doc->w && py < doc->h) {
                RGBA c = mergedPixel(px, py);
                if (c.a) (downAlt ? secondary : primary) = RGBA{c.r, c.g, c.b, 255};
            }
            break;
        }
        case Tool::Brush:
        case Tool::Pencil:
        case Tool::Eraser:
        case Tool::Clone:
        case Tool::SpotHeal:
            if (live == Live::Stroke) {
                float dx = p.x - stroker.last.x, dy = p.y - stroker.last.y;
                if (dx * dx + dy * dy > 0.25f) strokeDir = std::atan2(dy, dx) * 180.f / kPi;
                stroker.to(p, spacingPx(), [this](Vec2 q) { brushDab(q); });
            }
            break;
        case Tool::Blur:
        case Tool::Sharpen:
        case Tool::Smudge:
        case Tool::Dodge:
        case Tool::Burn:
        case Tool::Sponge:
            if (retouching) stroker.to(p, std::max(1.f, brush().preset.size * 0.12f), [this](Vec2 q) { retouchDab(q); });
            break;
        case Tool::Gradient:
            if (live == Live::Stroke) {
                gradB = shiftNow ? constrain45(gradA, p) : p;
                invalidateAll();
            }
            break;
        case Tool::Shape: {
            if (live != Live::Stroke) break;
            invalidate(cov.touched);
            cov.clear();
            Vec2 b = p;
            if (shiftNow) b = (shapeKind == ShapeKind::Line || shapeKind == ShapeKind::Arrow) ? constrain45(downPt, p) : constrainSquare(downPt, p);
            drawShapeCoverage(downPt, b);
            invalidate(cov.touched);
            break;
        }
        default: break;
    }
}

void Editor::toolUp(Vec2 p) {
    bool shiftNow = ImGui::GetIO().KeyShift;
    switch (tool) {
        case Tool::Move:
            if (live != Live::Move) break;
            if (moveDx || moveDy) {
                doc->push("Перемещение");
                Image& L = doc->layer().img;
                L = std::move(moveBase);
                L.drawOver(moveFloat, moveDx, moveDy);
                if (doc->sel.active()) {
                    doc->sel.translate(moveDx, moveDy);
                    selectionChanged();
                }
                thumbsDirty = true;
            }
            live = Live::None;
            moveBase = {};
            moveFloat = {};
            invalidateAll();
            break;
        case Tool::RectSelect:
        case Tool::EllipseSelect: {
            Vec2 b = (shiftNow && !downShift) ? constrainSquare(downPt, p) : p;
            Selection::Op op = selOpFromMods();
            if (std::fabs(b.x - downPt.x) < 1 && std::fabs(b.y - downPt.y) < 1) {
                if (op == Selection::Op::Replace) cmdDeselect();
                break;
            }
            Coverage c;
            c.reset(doc->w, doc->h);
            if (tool == Tool::RectSelect) {
                Rect r = rectFrom(downPt, b);
                c.rect(float(r.x0), float(r.y0), float(r.x1), float(r.y1), true, 0);
            } else {
                c.ellipse(downPt.x, downPt.y, b.x, b.y, true, 0);
            }
            combineSelection(std::move(c.v), op);
            break;
        }
        case Tool::Lasso: {
            Selection::Op op = selOpFromMods();
            if (lasso.size() < 3) {
                if (op == Selection::Op::Replace) cmdDeselect();
            } else {
                Coverage c;
                c.reset(doc->w, doc->h);
                c.polygonAA(lasso);
                combineSelection(std::move(c.v), op);
            }
            lasso.clear();
            break;
        }
        case Tool::Crop:
            cropMoving = false;
            if (cropRect.w() < 2 || cropRect.h() < 2) cropActive = false;
            break;
        case Tool::Brush: commitStroke("Кисть"); break;
        case Tool::Pencil: commitStroke("Карандаш"); break;
        case Tool::Eraser: commitStroke("Ластик"); break;
        case Tool::Clone:
            commitStroke("Штамп");
            cloneSnap = {};
            break;
        case Tool::SpotHeal:
            if (live == Live::Stroke && !cov.touched.empty()) {
                Coverage region = cov;
                cancelLive();
                doc->push("Точечное восстановление");
                Rect r = healRegion(doc->layer().img, region, doc->sel.mask);
                invalidate(r);
                thumbsDirty = true;
            }
            break;
        case Tool::Blur:
        case Tool::Sharpen:
        case Tool::Smudge:
        case Tool::Dodge:
        case Tool::Burn:
        case Tool::Sponge:
            retouching = false;
            thumbsDirty = true;
            break;
        case Tool::Gradient:
            if (std::hypot(gradB.x - gradA.x, gradB.y - gradA.y) < 1) cancelLive();
            else commitStroke("Градиент");
            break;
        case Tool::Shape:
            if (cov.touched.empty()) cancelLive();
            else {
                pushRecentColor(primary);
                commitStroke("Фигура", shapeNewLayer, "Фигура");
            }
            break;
        default: break;
    }
}

void Editor::finishPolyLasso() {
    Selection::Op op = selOpFromMods();
    if (lasso.size() >= 3) {
        Coverage c;
        c.reset(doc->w, doc->h);
        c.polygonAA(lasso);
        combineSelection(std::move(c.v), op);
    }
    lasso.clear();
    polyActive = false;
}

void Editor::applyCrop() {
    if (!cropActive || cropRect.empty()) return;
    Rect r = cropRect;
    cropActive = false;
    imageAction("Кадрирование", [r](Document& d) { d.crop(r); });
}

// ---------------------------------------------------------------- text

const Font* Editor::currentFont() {
    if (fonts.empty()) return nullptr;
    fontIndex = std::clamp(fontIndex, 0, int(fonts.size()) - 1);
    const std::string& path = fonts[size_t(fontIndex)].path;
    auto it = fontCache.find(path);
    if (it == fontCache.end()) {
        Font f;
        f.load(path);
        it = fontCache.emplace(path, std::move(f)).first;
    }
    return it->second.ok() ? &it->second : nullptr;
}

void Editor::textPreview() {
    if (!textEditing || !doc) return;
    if (live != Live::Stroke) beginStroke(Source::Solid, primary, 1.f);
    invalidate(cov.touched);
    cov.clear();
    liveColor = primary;
    if (const Font* f = currentFont()) f->draw(&cov, textBuf, textPos.x, textPos.y, fontSize);
    invalidate(cov.touched);
}

void Editor::commitText() {
    if (!textEditing) return;
    textEditing = false;
    if (textBuf.find_first_not_of(" \n\r\t") == std::string::npos) return cancelLive();
    textEditing = true;
    textPreview();
    textEditing = false;
    pushRecentColor(primary);
    commitStroke("Текст", true, utf8Prefix(textBuf.substr(0, textBuf.find('\n')), 24));
}

void Editor::cancelText() {
    if (!textEditing) return;
    textEditing = false;
    cancelLive();
}

// ---------------------------------------------------------------- overlays

void Editor::rebuildAnts() {
    selOutlineDirty = false;
    antSegments.clear();
    if (!doc || !doc->sel.active()) return;
    const Selection& s = doc->sel;
    int w = s.w, h = s.h;
    auto in = [&](int x, int y) { return x >= 0 && y >= 0 && x < w && y < h && s.mask[size_t(y) * w + x] >= 128; };
    for (int y = 0; y <= h; y++) {
        int start = -1;
        for (int x = 0; x <= w; x++) {
            bool edge = x < w && in(x, y - 1) != in(x, y);
            if (edge && start < 0) start = x;
            if (!edge && start >= 0) {
                antSegments.push_back(ImVec4(float(start), float(y), float(x), float(y)));
                start = -1;
            }
        }
    }
    for (int x = 0; x <= w; x++) {
        int start = -1;
        for (int y = 0; y <= h; y++) {
            bool edge = y < h && in(x - 1, y) != in(x, y);
            if (edge && start < 0) start = y;
            if (!edge && start >= 0) {
                antSegments.push_back(ImVec4(float(x), float(start), float(x), float(y)));
                start = -1;
            }
        }
    }
}

void Editor::drawOverlays(ImDrawList* dl) {
    const ImU32 black = IM_COL32(0, 0, 0, 255), white = IM_COL32(255, 255, 255, 255);
    ImGuiIO& io = ImGui::GetIO();
    ImVec2 cmin = canvasMin, cmax(canvasMin.x + canvasSize.x, canvasMin.y + canvasSize.y);
    float t = float(ImGui::GetTime());

    auto ants = [&](ImVec2 a, ImVec2 b) {
        dl->AddLine(a, b, black);
        float len = std::hypot(b.x - a.x, b.y - a.y);
        if (len < 1) return;
        float dx = (b.x - a.x) / len, dy = (b.y - a.y) / len;
        float phase = std::fmod(a.x + a.y + t * 16.f, 8.f);
        for (float s = -phase; s < len; s += 8.f) {
            float s0 = std::max(0.f, s), s1 = std::min(len, s + 4.f);
            if (s1 > s0) dl->AddLine(ImVec2(a.x + dx * s0, a.y + dy * s0), ImVec2(a.x + dx * s1, a.y + dy * s1), white);
        }
    };

    if (showGrid && zoom >= 8.f) {
        ImU32 g = IM_COL32(128, 128, 128, 90);
        Vec2 a = toDoc(cmin), b = toDoc(cmax);
        for (int x = std::max(0, int(a.x)); x <= std::min(doc->w, int(b.x) + 1); x++)
            dl->AddLine(toScreen({float(x), 0}), toScreen({float(x), float(doc->h)}), g);
        for (int y = std::max(0, int(a.y)); y <= std::min(doc->h, int(b.y) + 1); y++)
            dl->AddLine(toScreen({0, float(y)}), toScreen({float(doc->w), float(y)}), g);
    }

    if (selOutlineDirty) rebuildAnts();
    bool many = antSegments.size() > 40000;
    for (const ImVec4& s : antSegments) {
        ImVec2 a = toScreen({s.x, s.y}), b = toScreen({s.z, s.w});
        if (std::max(a.x, b.x) < cmin.x || std::min(a.x, b.x) > cmax.x || std::max(a.y, b.y) < cmin.y ||
            std::min(a.y, b.y) > cmax.y)
            continue;
        if (many) dl->AddLine(a, b, black);
        else ants(a, b);
    }

    if (dragging && (tool == Tool::RectSelect || tool == Tool::EllipseSelect)) {
        Vec2 b = (io.KeyShift && !downShift) ? constrainSquare(downPt, curPt) : curPt;
        ImVec2 a = toScreen(downPt), c = toScreen(b);
        if (tool == Tool::RectSelect) {
            ants(a, ImVec2(c.x, a.y)); ants(ImVec2(c.x, a.y), c); ants(c, ImVec2(a.x, c.y)); ants(ImVec2(a.x, c.y), a);
        } else {
            ImVec2 ctr((a.x + c.x) * 0.5f, (a.y + c.y) * 0.5f);
            float rx = std::fabs(c.x - a.x) * 0.5f, ry = std::fabs(c.y - a.y) * 0.5f;
            const int N = 64;
            for (int i = 0; i < N; i++) {
                float a0 = i * 2 * kPi / N, a1 = (i + 1) * 2 * kPi / N;
                ants(ImVec2(ctr.x + std::cos(a0) * rx, ctr.y + std::sin(a0) * ry),
                     ImVec2(ctr.x + std::cos(a1) * rx, ctr.y + std::sin(a1) * ry));
            }
        }
    }
    if ((tool == Tool::Lasso || tool == Tool::PolyLasso) && !lasso.empty()) {
        for (size_t i = 1; i < lasso.size(); i++) ants(toScreen(lasso[i - 1]), toScreen(lasso[i]));
        if (tool == Tool::PolyLasso && polyActive) {
            ants(toScreen(lasso.back()), io.MousePos);
            dl->AddCircle(toScreen(lasso.front()), 5, white, 0, 1.5f);
        }
    }

    if (cropActive && !cropRect.empty()) {
        ImVec2 a = toScreen({float(cropRect.x0), float(cropRect.y0)}), b = toScreen({float(cropRect.x1), float(cropRect.y1)});
        ImVec2 da = toScreen({0, 0}), db = toScreen({float(doc->w), float(doc->h)});
        ImU32 shade = IM_COL32(0, 0, 0, 150);
        dl->AddRectFilled(da, ImVec2(db.x, a.y), shade);
        dl->AddRectFilled(ImVec2(da.x, b.y), db, shade);
        dl->AddRectFilled(ImVec2(da.x, a.y), ImVec2(a.x, b.y), shade);
        dl->AddRectFilled(ImVec2(b.x, a.y), ImVec2(db.x, b.y), shade);
        dl->AddRect(a, b, white, 0, 0, 1.5f);
        for (int i = 1; i < 3; i++) {
            float x = a.x + (b.x - a.x) * i / 3, y = a.y + (b.y - a.y) * i / 3;
            dl->AddLine(ImVec2(x, a.y), ImVec2(x, b.y), IM_COL32(255, 255, 255, 70));
            dl->AddLine(ImVec2(a.x, y), ImVec2(b.x, y), IM_COL32(255, 255, 255, 70));
        }
        float hs = 5;
        for (ImVec2 c : {a, b, ImVec2(a.x, b.y), ImVec2(b.x, a.y)})
            dl->AddRectFilled(ImVec2(c.x - hs, c.y - hs), ImVec2(c.x + hs, c.y + hs), white, 2);
        char buf[64];
        std::snprintf(buf, sizeof buf, "%d × %d", cropRect.w(), cropRect.h());
        ImVec2 ts = ImGui::CalcTextSize(buf);
        dl->AddRectFilled(ImVec2(a.x + 4, a.y + 4), ImVec2(a.x + ts.x + 14, a.y + ts.y + 10), IM_COL32(0, 0, 0, 170), 6);
        dl->AddText(ImVec2(a.x + 9, a.y + 7), white, buf);
    }

    if (tool == Tool::Gradient && dragging && live == Live::Stroke) {
        ImVec2 a = toScreen(gradA), b = toScreen(gradB);
        dl->AddLine(a, b, black, 3.f);
        dl->AddLine(a, b, white, 1.f);
        dl->AddCircleFilled(a, 5, white);
        dl->AddCircle(a, 5, black);
        dl->AddCircleFilled(b, 5, black);
        dl->AddCircle(b, 5, white);
    }

    if (textEditing) {
        Rect r = cov.touched.empty() ? Rect::of(int(textPos.x), int(textPos.y), int(fontSize * 0.6f), int(fontSize * 1.2f))
                                     : cov.touched;
        r = r.unite(Rect::of(int(textPos.x), int(textPos.y), 1, int(fontSize * 1.2f)));
        ImVec2 a = toScreen({float(r.x0) - 2, float(r.y0) - 2}), b = toScreen({float(r.x1) + 2, float(r.y1) + 2});
        dl->AddRect(a, b, IM_COL32(38, 128, 235, 255), 3, 0, 1.5f);
    }

    bool hovered = io.MousePos.x >= cmin.x && io.MousePos.y >= cmin.y && io.MousePos.x < cmax.x && io.MousePos.y < cmax.y;
    if (tool == Tool::Clone && cloneHasSource) {
        Vec2 s = cloneAligned ? Vec2{curPt.x + cloneDx, curPt.y + cloneDy} : cloneSource;
        ImVec2 c = toScreen(s);
        dl->AddLine(ImVec2(c.x - 7, c.y), ImVec2(c.x + 7, c.y), black, 3.f);
        dl->AddLine(ImVec2(c.x, c.y - 7), ImVec2(c.x, c.y + 7), black, 3.f);
        dl->AddLine(ImVec2(c.x - 6, c.y), ImVec2(c.x + 6, c.y), white);
        dl->AddLine(ImVec2(c.x, c.y - 6), ImVec2(c.x, c.y + 6), white);
    }

    if ((hovered || dragging) && !panning && !ImGui::IsKeyDown(ImGuiKey_Space)) {
        ImVec2 m = io.MousePos;
        if (isBrushTool(tool)) {
            const BrushPreset& pr = brush().preset;
            float r = pr.size * 0.5f * zoom;
            if (r >= 3.f) {
                if (pr.roundness < 0.98f) {  // show the tip's ellipse
                    float a = pr.angle * kPi / 180.f;
                    ImVec2 pts[48];
                    for (int i = 0; i < 48; i++) {
                        float th = i * 2 * kPi / 48, u = std::cos(th) * r, v = std::sin(th) * r * pr.roundness;
                        pts[i] = ImVec2(m.x + u * std::cos(a) - v * std::sin(a), m.y + u * std::sin(a) + v * std::cos(a));
                    }
                    dl->AddPolyline(pts, 48, black, ImDrawFlags_Closed, 2.f);
                    dl->AddPolyline(pts, 48, white, ImDrawFlags_Closed, 1.f);
                } else {
                    dl->AddCircle(m, r + 1, black, 0, 1.f);
                    dl->AddCircle(m, r, white, 0, 1.f);
                }
            }
        }
        if (tool != Tool::Move && tool != Tool::Hand && tool != Tool::Text && tool != Tool::Zoom) {
            dl->AddLine(ImVec2(m.x - 6, m.y), ImVec2(m.x + 7, m.y), black, 3.f);
            dl->AddLine(ImVec2(m.x, m.y - 6), ImVec2(m.x, m.y + 7), black, 3.f);
            dl->AddLine(ImVec2(m.x - 5, m.y), ImVec2(m.x + 6, m.y), white);
            dl->AddLine(ImVec2(m.x, m.y - 5), ImVec2(m.x, m.y + 6), white);
        }
    }
}

}  // namespace ag
