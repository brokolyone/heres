#pragma once
#include <vector>

#include "gradient.h"
#include "image.h"

namespace ag {

// Non-destructive layer styles. Rendered from the layer's pixels when compositing.
struct LayerFx {
    struct Shadow {
        bool on = false;
        RGBA color{0, 0, 0, 255};
        float opacity = 0.75f, angle = 120.f, distance = 12.f, size = 14.f, spread = 0.f;
    } dropShadow;
    struct Glow {
        bool on = false;
        RGBA color{255, 236, 140, 255};
        float opacity = 0.75f, size = 16.f, spread = 0.f;
    } outerGlow, innerGlow;
    struct Bevel {
        bool on = false;
        float size = 10.f, depth = 100.f, angle = 120.f, altitude = 30.f;
        float highlight = 0.75f, shadow = 0.75f;
    } bevel;
    struct Stroke {
        bool on = false;
        RGBA color{0, 0, 0, 255};
        float size = 4.f, opacity = 1.f;
        int position = 0;  // 0 outside, 1 center, 2 inside
    } stroke;
    struct ColorOverlay {
        bool on = false;
        RGBA color{38, 128, 235, 255};
        float opacity = 1.f;
    } colorOverlay;
    struct GradientOverlay {
        bool on = false;
        Gradient gradient{"", {{0, {20, 70, 160, 255}}, {1, {80, 180, 245, 255}}}};
        GradientType type = GradientType::Linear;
        float angle = 90.f, opacity = 1.f;
    } gradientOverlay;

    bool any() const {
        return dropShadow.on || outerGlow.on || innerGlow.on || bevel.on || stroke.on || colorOverlay.on || gradientOverlay.on;
    }
};

// Renders the styled layer (same size as src).
Image renderLayerFx(const Image& src, const LayerFx& fx);

// Euclidean distance (in px) from every pixel to the nearest pixel where `inside` is true.
std::vector<float> distanceTransform(const std::vector<uint8_t>& inside, int w, int h);

}  // namespace ag
