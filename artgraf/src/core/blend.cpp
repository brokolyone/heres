#include "blend.h"

#include <cmath>
#include <cstring>

namespace ag {

namespace {
struct ModeInfo { const char* name; const char* id; };
const ModeInfo kModes[] = {
    {"Обычный", "normal"},         {"Затемнение", "darken"},     {"Умножение", "multiply"},
    {"Затемнение основы", "color-burn"}, {"Линейный затемнитель", "linear-burn"},
    {"Замена светлым", "lighten"}, {"Экран", "screen"},          {"Осветление основы", "color-dodge"},
    {"Линейный осветлитель", "add"},
    {"Перекрытие", "overlay"},     {"Мягкий свет", "soft-light"}, {"Жёсткий свет", "hard-light"},
    {"Разница", "difference"},     {"Исключение", "exclusion"},  {"Вычитание", "subtract"},
};
static_assert(sizeof(kModes) / sizeof(kModes[0]) == size_t(BlendMode::Count));

float channel(float b, float s, BlendMode m) {
    switch (m) {
        case BlendMode::Normal: return s;
        case BlendMode::Darken: return std::min(b, s);
        case BlendMode::Multiply: return b * s;
        case BlendMode::ColorBurn:
            if (b >= 1.f) return 1.f;
            if (s <= 0.f) return 0.f;
            return 1.f - std::min(1.f, (1.f - b) / s);
        case BlendMode::LinearBurn: return std::max(0.f, b + s - 1.f);
        case BlendMode::Lighten: return std::max(b, s);
        case BlendMode::Screen: return b + s - b * s;
        case BlendMode::ColorDodge:
            if (b <= 0.f) return 0.f;
            if (s >= 1.f) return 1.f;
            return std::min(1.f, b / (1.f - s));
        case BlendMode::Add: return std::min(1.f, b + s);
        case BlendMode::Overlay: return channel(s, b, BlendMode::HardLight);
        case BlendMode::HardLight:
            return s <= 0.5f ? b * 2.f * s : channel(b, 2.f * s - 1.f, BlendMode::Screen);
        case BlendMode::SoftLight: {
            if (s <= 0.5f) return b - (1.f - 2.f * s) * b * (1.f - b);
            float d = b <= 0.25f ? ((16.f * b - 12.f) * b + 4.f) * b : std::sqrt(b);
            return b + (2.f * s - 1.f) * (d - b);
        }
        case BlendMode::Difference: return std::fabs(b - s);
        case BlendMode::Exclusion: return b + s - 2.f * b * s;
        case BlendMode::Subtract: return std::max(0.f, b - s);
        default: return s;
    }
}
}  // namespace

const char* blendName(BlendMode m) { return kModes[int(m)].name; }
const char* blendId(BlendMode m) { return kModes[int(m)].id; }

BlendMode blendFromId(const char* id) {
    for (int i = 0; i < int(BlendMode::Count); i++)
        if (std::strcmp(kModes[i].id, id) == 0) return BlendMode(i);
    return BlendMode::Normal;
}

RGBA blendPixel(RGBA d, RGBA s, BlendMode mode, float opacity) {
    if (mode == BlendMode::Normal) return over(d, s, opacity);
    float as = s.a / 255.f * opacity;
    if (as <= 0.f) return d;
    float ab = d.a / 255.f;
    float ao = as + ab * (1.f - as);
    if (ao <= 0.f) return {};
    float sc[3] = {s.r / 255.f, s.g / 255.f, s.b / 255.f};
    float bc[3] = {d.r / 255.f, d.g / 255.f, d.b / 255.f};
    uint8_t out[3];
    for (int i = 0; i < 3; i++) {
        float mixed = channel(bc[i], sc[i], mode);
        float c = ((1.f - ab) * as * sc[i] + (1.f - as) * ab * bc[i] + as * ab * mixed) / ao;
        out[i] = clamp8(c * 255.f);
    }
    return {out[0], out[1], out[2], clamp8(ao * 255.f)};
}

}  // namespace ag
