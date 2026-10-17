#include "gradient.h"

#include <algorithm>
#include <cmath>

namespace ag {

RGBA Gradient::sample(float t) const {
    if (stops.empty()) return {};
    t = std::clamp(t, 0.f, 1.f);
    if (t <= stops.front().pos) return stops.front().color;
    if (t >= stops.back().pos) return stops.back().color;
    for (size_t i = 1; i < stops.size(); i++) {
        const GradientStop &a = stops[i - 1], &b = stops[i];
        if (t <= b.pos) {
            float k = b.pos > a.pos ? (t - a.pos) / (b.pos - a.pos) : 0.f;
            // Interpolate color weighted by alpha so fading to transparent keeps the hue.
            float aa = a.color.a / 255.f, ba = b.color.a / 255.f;
            float oa = aa + (ba - aa) * k;
            RGBA o;
            o.a = clamp8(oa * 255);
            if (oa <= 0.0001f) return {a.color.r, a.color.g, a.color.b, 0};
            auto ch = [&](uint8_t x, uint8_t y) {
                float wa = aa > 0 || ba > 0 ? aa : 1, wb = aa > 0 || ba > 0 ? ba : 1;
                float num = x * wa * (1 - k) + y * wb * k, den = wa * (1 - k) + wb * k;
                return clamp8(den > 0 ? num / den : x);
            };
            o.r = ch(a.color.r, b.color.r);
            o.g = ch(a.color.g, b.color.g);
            o.b = ch(a.color.b, b.color.b);
            return o;
        }
    }
    return stops.back().color;
}

void Gradient::sort() {
    std::stable_sort(stops.begin(), stops.end(), [](const GradientStop& a, const GradientStop& b) { return a.pos < b.pos; });
}

Gradient Gradient::reversed() const {
    Gradient g = *this;
    for (auto& s : g.stops) s.pos = 1 - s.pos;
    g.sort();
    return g;
}

const char* gradientTypeName(GradientType t) {
    static const char* names[] = {"Линейный", "Радиальный", "Угловой", "Зеркальный", "Ромбовидный"};
    return names[int(t)];
}

float gradientT(GradientType type, float ax, float ay, float bx, float by, float px, float py) {
    float vx = bx - ax, vy = by - ay;
    float len2 = vx * vx + vy * vy;
    if (len2 < 0.25f) return 0.f;
    float len = std::sqrt(len2);
    float dx = px - ax, dy = py - ay;
    float t = 0;
    switch (type) {
        case GradientType::Linear: t = (dx * vx + dy * vy) / len2; break;
        case GradientType::Radial: t = std::sqrt(dx * dx + dy * dy) / len; break;
        case GradientType::Angle: {
            float a = std::atan2(dy, dx) - std::atan2(vy, vx);
            t = a / (2 * 3.14159265f);
            t -= std::floor(t);
            break;
        }
        case GradientType::Reflected: t = std::fabs((dx * vx + dy * vy) / len2); break;
        case GradientType::Diamond: {
            float ux = vx / len, uy = vy / len;
            float along = std::fabs(dx * ux + dy * uy), across = std::fabs(-dx * uy + dy * ux);
            t = (along + across) / len;
            break;
        }
        default: break;
    }
    return std::clamp(t, 0.f, 1.f);
}

std::vector<Gradient> gradientPresets(RGBA p, RGBA s) {
    auto hex = [](uint32_t c, uint8_t a = 255) { return RGBA{uint8_t(c >> 16), uint8_t(c >> 8), uint8_t(c), a}; };
    auto even = [&](const char* name, std::initializer_list<uint32_t> colors) {
        Gradient g;
        g.name = name;
        int n = int(colors.size()), i = 0;
        for (uint32_t c : colors) g.stops.push_back({n > 1 ? float(i++) / (n - 1) : 0.f, hex(c)});
        return g;
    };
    std::vector<Gradient> v;
    v.push_back({"Основной → фоновый", {{0, p}, {1, s}}});
    v.push_back({"Основной → прозрачный", {{0, p}, {1, {p.r, p.g, p.b, 0}}}});
    v.push_back(even("Чёрный → белый", {0x000000, 0xffffff}));
    v.push_back(even("Радуга", {0xff0000, 0xff8000, 0xffff00, 0x00c000, 0x00a0ff, 0x4000ff, 0xc000ff}));
    v.push_back(even("Закат", {0x2b1055, 0x7f1f6e, 0xd8345f, 0xf28f3b, 0xffd46b}));
    v.push_back(even("Океан", {0x021b3a, 0x064f8c, 0x1fa2c7, 0x9be7ef}));
    v.push_back(even("Хром", {0x2c2c2c, 0xf0f0f0, 0x6e6e6e, 0xffffff, 0x3a3a3a}));
    v.push_back(even("Медь", {0x5a2a12, 0xc8743a, 0xffd2a8, 0x9a4a1e}));
    v.push_back(even("Золото", {0x6b4a12, 0xd8a83a, 0xfff0b0, 0xb07a1a}));
    v.push_back(even("Неон", {0xff00cc, 0x7a00ff, 0x00e5ff}));
    v.push_back(even("Пастель", {0xffd1dc, 0xfff1b5, 0xc6f1d6, 0xc5d8ff}));
    v.push_back(even("Огонь", {0x200000, 0xa00000, 0xff5a00, 0xffd000, 0xffffc0}));
    v.push_back(even("Лёд", {0xffffff, 0xbfefff, 0x5ac8fa, 0x0a3d91}));
    v.push_back(even("Лес", {0x0b2b16, 0x2f6b2a, 0x8fbf4a, 0xe8f0a0}));
    v.push_back(even("Фиолетовый туман", {0x120c2c, 0x4b2c8a, 0xb284e6, 0xf0e0ff}));
    Gradient fade{"Прозрачные полосы", {}};
    for (int i = 0; i <= 8; i++) fade.stops.push_back({i / 8.f, {p.r, p.g, p.b, uint8_t(i % 2 ? 0 : 255)}});
    v.push_back(fade);
    return v;
}

}  // namespace ag
