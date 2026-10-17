#include "icons.h"

#include <cmath>

namespace ag {

namespace {

struct Pen {
    ImDrawList* dl;
    ImVec2 c;
    float s;  // half size
    ImU32 col;
    float th;

    ImVec2 P(float x, float y) const { return ImVec2(c.x + x * s, c.y + y * s); }
    void line(float x0, float y0, float x1, float y1, float t = 0) const { dl->AddLine(P(x0, y0), P(x1, y1), col, t > 0 ? t : th); }
    void rect(float x0, float y0, float x1, float y1) const { dl->AddRect(P(x0, y0), P(x1, y1), col, 0, 0, th); }
    void fillRect(float x0, float y0, float x1, float y1) const { dl->AddRectFilled(P(x0, y0), P(x1, y1), col); }
    void circle(float x, float y, float r) const { dl->AddCircle(P(x, y), r * s, col, 0, th); }
    void fillCircle(float x, float y, float r) const { dl->AddCircleFilled(P(x, y), r * s, col); }
    void poly(std::initializer_list<ImVec2> pts, bool fill) const {
        ImVec2 buf[16];
        int n = 0;
        for (auto& p : pts) buf[n++] = P(p.x, p.y);
        if (fill) dl->AddConvexPolyFilled(buf, n, col);
        else dl->AddPolyline(buf, n, col, ImDrawFlags_Closed, th);
    }
    void dashedLine(float x0, float y0, float x1, float y1, int dashes) const {
        for (int i = 0; i < dashes; i++) {
            float a = float(i) / dashes, b = (i + 0.55f) / dashes;
            line(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a, x0 + (x1 - x0) * b, y0 + (y1 - y0) * b);
        }
    }
    void arrowHead(float x, float y, float dx, float dy) const {
        float k = 0.28f;
        poly({{x, y}, {x - dx * k - dy * k, y - dy * k + dx * k}, {x - dx * k + dy * k, y - dy * k - dx * k}}, true);
    }
};

}  // namespace

void drawToolIcon(ImDrawList* dl, Tool tool, ImVec2 center, float size, ImU32 col) {
    Pen p{dl, center, size * 0.5f, col, std::max(1.f, size / 14.f)};
    switch (tool) {
        case Tool::Move:
            p.line(-0.85f, 0, 0.85f, 0);
            p.line(0, -0.85f, 0, 0.85f);
            p.arrowHead(0.95f, 0, 1, 0);
            p.arrowHead(-0.95f, 0, -1, 0);
            p.arrowHead(0, 0.95f, 0, 1);
            p.arrowHead(0, -0.95f, 0, -1);
            break;
        case Tool::RectSelect:
            p.dashedLine(-0.8f, -0.65f, 0.8f, -0.65f, 4);
            p.dashedLine(-0.8f, 0.65f, 0.8f, 0.65f, 4);
            p.dashedLine(-0.8f, -0.65f, -0.8f, 0.65f, 3);
            p.dashedLine(0.8f, -0.65f, 0.8f, 0.65f, 3);
            break;
        case Tool::EllipseSelect:
            for (int i = 0; i < 12; i += 1) {
                float a0 = i * 6.2832f / 12, a1 = (i + 0.55f) * 6.2832f / 12;
                p.line(std::cos(a0) * 0.85f, std::sin(a0) * 0.65f, std::cos(a1) * 0.85f, std::sin(a1) * 0.65f);
            }
            break;
        case Tool::Lasso: {
            ImVec2 pts[24];
            for (int i = 0; i < 20; i++) {
                float a = 0.9f + i * 5.6f / 19;
                pts[i] = p.P(std::cos(a) * 0.8f, -0.25f + std::sin(a) * 0.5f);
            }
            dl->AddPolyline(pts, 20, col, 0, p.th);
            dl->AddBezierCubic(p.P(0.5f, 0.15f), p.P(0.2f, 0.5f), p.P(-0.4f, 0.4f), p.P(-0.15f, 0.9f), col, p.th);
            break;
        }
        case Tool::MagicWand:
            p.line(-0.8f, 0.8f, 0.25f, -0.25f, p.th * 1.6f);
            p.line(0.55f, -0.95f, 0.55f, -0.15f);
            p.line(0.15f, -0.55f, 0.95f, -0.55f);
            p.line(0.27f, -0.83f, 0.83f, -0.27f, p.th * 0.7f);
            p.line(0.27f, -0.27f, 0.83f, -0.83f, p.th * 0.7f);
            break;
        case Tool::Crop:
            p.line(-0.5f, -0.95f, -0.5f, 0.5f);
            p.line(-0.5f, 0.5f, 0.95f, 0.5f);
            p.line(-0.95f, -0.5f, 0.5f, -0.5f);
            p.line(0.5f, -0.5f, 0.5f, 0.95f);
            break;
        case Tool::Eyedropper:
            p.line(-0.75f, 0.75f, 0.2f, -0.2f, p.th * 1.4f);
            p.line(-0.05f, -0.45f, 0.45f, 0.05f, p.th * 1.4f);
            p.fillCircle(0.45f, -0.45f, 0.32f);
            p.fillCircle(-0.8f, 0.8f, 0.1f);
            break;
        case Tool::Brush:
            p.line(0.85f, -0.85f, -0.05f, 0.1f, p.th * 1.4f);
            p.poly({{-0.15f, 0.0f}, {0.1f, 0.25f}, {-0.3f, 0.75f}, {-0.85f, 0.85f}, {-0.7f, 0.35f}}, true);
            break;
        case Tool::Pencil:
            p.poly({{0.55f, -0.85f}, {0.85f, -0.55f}, {-0.45f, 0.75f}, {-0.75f, 0.45f}}, false);
            p.poly({{-0.75f, 0.45f}, {-0.45f, 0.75f}, {-0.9f, 0.9f}}, true);
            p.line(0.35f, -0.65f, 0.65f, -0.35f);
            break;
        case Tool::Eraser:
            p.poly({{0.2f, -0.8f}, {0.9f, -0.1f}, {0.1f, 0.7f}, {-0.6f, 0.0f}}, false);
            p.poly({{-0.6f, 0.0f}, {-0.25f, -0.35f}, {0.45f, 0.35f}, {0.1f, 0.7f}}, true);
            p.line(-0.9f, 0.85f, 0.9f, 0.85f);
            break;
        case Tool::Clone:
            p.circle(0, -0.6f, 0.28f);
            p.line(0, -0.32f, 0, 0.05f, p.th * 1.6f);
            p.poly({{-0.75f, 0.05f}, {0.75f, 0.05f}, {0.75f, 0.45f}, {-0.75f, 0.45f}}, true);
            p.line(-0.85f, 0.75f, 0.85f, 0.75f);
            break;
        case Tool::Gradient: {
            ImVec4 c = ImGui::ColorConvertU32ToFloat4(col);
            ImU32 clear = ImGui::GetColorU32(ImVec4(c.x, c.y, c.z, 0.05f));
            dl->AddRectFilledMultiColor(p.P(-0.85f, -0.65f), p.P(0.85f, 0.65f), col, clear, clear, col);
            p.rect(-0.85f, -0.65f, 0.85f, 0.65f);
            break;
        }
        case Tool::Bucket:
            p.poly({{-0.55f, -0.55f}, {0.35f, -0.1f}, {-0.05f, 0.75f}, {-0.9f, 0.3f}}, false);
            p.line(-0.55f, -0.55f, -0.25f, -0.95f);
            p.dl->AddBezierQuadratic(p.P(0.35f, -0.1f), p.P(0.85f, 0.1f), p.P(0.75f, 0.55f), col, p.th);
            p.fillCircle(0.75f, 0.65f, 0.14f);
            break;
        case Tool::Text:
            p.line(-0.7f, -0.75f, 0.7f, -0.75f, p.th * 1.5f);
            p.line(0, -0.75f, 0, 0.8f, p.th * 1.5f);
            p.line(-0.25f, 0.8f, 0.25f, 0.8f);
            p.line(-0.7f, -0.75f, -0.7f, -0.5f);
            p.line(0.7f, -0.75f, 0.7f, -0.5f);
            break;
        case Tool::Shape:
            p.fillRect(-0.85f, -0.85f, 0.25f, 0.25f);
            p.circle(0.3f, 0.3f, 0.55f);
            break;
        case Tool::Hand:
            p.dl->AddRect(p.P(-0.5f, -0.1f), p.P(0.55f, 0.9f), col, 0.35f * p.s, 0, p.th);
            for (int i = 0; i < 4; i++) {
                float x = -0.38f + i * 0.28f;
                p.line(x, -0.1f, x, i == 0 || i == 3 ? -0.55f : -0.8f);
            }
            p.line(-0.5f, 0.35f, -0.85f, 0.0f);
            break;
        case Tool::Zoom:
            p.circle(-0.2f, -0.2f, 0.55f);
            p.line(0.2f, 0.2f, 0.85f, 0.85f, p.th * 1.8f);
            p.line(-0.45f, -0.2f, 0.05f, -0.2f);
            p.line(-0.2f, -0.45f, -0.2f, 0.05f);
            break;
        default: break;
    }
}

void drawLogo(ImDrawList* dl, ImVec2 mn, float size) {
    ImVec2 mx(mn.x + size, mn.y + size);
    dl->AddRectFilledMultiColor(mn, mx, IM_COL32(61, 139, 253, 255), IM_COL32(139, 92, 246, 255),
                                IM_COL32(219, 70, 160, 255), IM_COL32(61, 139, 253, 255));
    Pen p{dl, ImVec2(mn.x + size * 0.5f, mn.y + size * 0.5f), size * 0.5f, IM_COL32_WHITE, std::max(1.5f, size / 9.f)};
    p.line(-0.5f, 0.6f, 0.0f, -0.6f);
    p.line(0.0f, -0.6f, 0.5f, 0.6f);
    p.line(-0.27f, 0.12f, 0.27f, 0.12f);
    dl->AddBezierCubic(p.P(-0.7f, 0.82f), p.P(-0.2f, 0.6f), p.P(0.2f, 1.0f), p.P(0.72f, 0.75f), IM_COL32(255, 255, 255, 200),
                       p.th * 0.7f);
}

}  // namespace ag
